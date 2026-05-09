"""백엔드 오케스트레이터.

PlayerManager를 보유하고 비전 이벤트(seat_right_registered, seat_registered)를 소비해
플레이어 좌석 등록을 진행/완료한다. phase 전환을 관리하고 프론트로 state_update push.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable

from backend.state import build_state_snapshot
from core.constants import CommonEventType, CommonPhase
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from core.models import SeatZone
from core.player_manager import PlayerManager
from games.werewolf.fsm import WerewolfFSM
from games.werewolf.ontology import WerewolfEventType, WerewolfInputType
from games.werewolf.state import WerewolfPlayerState

# 역할 등록 phase 식별자 (CommonPhase에 없는 내부 확장 값)
_PHASE_ROLE_REGISTRATION = "role_registration"


def _normalize_role(role_id: str) -> str:
    """프론트 role id (werewolf_1, mason_2 등) → FSM role 문자열 (werewolf, mason)."""
    import re
    return re.sub(r"_\d+$", "", role_id)


class Orchestrator:
    def __init__(self, send_fusion_context_fn: Callable[[FusionContext, int], None]) -> None:
        self._pm = PlayerManager()
        self._send_fusion_context = send_fusion_context_fn
        self._lock = threading.Lock()
        self._broadcast_cb: Callable[[dict], None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._phase = CommonPhase.PLAYER_SETUP
        self._state_version = 0
        # 좌석 등록 단계: idle | right_pending | right_done | completed
        self._seat_step = "idle"
        self._pending_register_id: str | None = None
        self._players_listener: Callable[[list], None] | None = None
        self._werewolf_fsm: WerewolfFSM | None = None
        # 역할 등록 단계 상태
        self._role_reg: dict | None = None
        # OK 사인 one-shot: 브로드캐스트 한 번 후 자동 소멸
        self._gesture_confirmed: str | None = None

    def set_broadcast(
        self,
        cb: Callable[[dict], None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._broadcast_cb = cb
        self._loop = loop

    def set_players_listener(self, cb: Callable[[list], None]) -> None:
        self._players_listener = cb

    def _notify_players(self) -> None:
        if self._players_listener is None:
            return
        registered = [p for p in self._pm.state.players if p.seat_zone is not None]
        with contextlib.suppress(Exception):
            self._players_listener(registered)

    # ── 비전 이벤트 소비 ───────────────────────────────────────────────────────────────────

    def handle_game_event(self, event: GameEvent, _state_version: int) -> None:
        if event.event_type == CommonEventType.SEAT_RIGHT_REGISTERED:
            self._handle_seat_right_registered(event)
        elif event.event_type == CommonEventType.SEAT_REGISTERED:
            self._handle_seat_registered(event)
        elif event.event_type == WerewolfEventType.ROLE_DETECTED:
            with self._lock:
                phase = self._phase
            if phase == _PHASE_ROLE_REGISTRATION:
                self._handle_role_detected(event)
        elif event.event_type == CommonEventType.GESTURE_CONFIRMED:
            self._handle_gesture_confirmed(event)
        elif event.event_type in (
            WerewolfEventType.CARD_PEEK,
            WerewolfEventType.CARD_SWAP,
            WerewolfEventType.VOTE_POINT,
        ):
            self._handle_werewolf_event(event)

    def _handle_seat_right_registered(self, event: GameEvent) -> None:
        actor_id = event.actor_id
        if not actor_id:
            return
        with self._lock:
            if self._pm.state.registering_player_id != actor_id:
                return
            self._seat_step = "right_done"
            snapshot = self._snapshot()
        self._broadcast(snapshot)

    def _handle_seat_registered(self, event: GameEvent) -> None:
        data = event.data or {}
        actor_id = event.actor_id
        seat_zone_d = data.get("seat_zone")
        if not actor_id or not seat_zone_d:
            return

        seat_zone = SeatZone.from_dict(seat_zone_d)

        with self._lock:
            try:
                self._pm.record_seat(actor_id, seat_zone)
            except KeyError:
                return

            self._phase = CommonPhase.PLAYER_SETUP
            self._seat_step = "completed"
            snapshot = self._snapshot(sound="registered")

        self._push_context(CommonPhase.PLAYER_SETUP)
        self._notify_players()
        self._broadcast(snapshot)

    def _handle_role_detected(self, event: GameEvent) -> None:
        """역할 등록 단계에서 ROLE_DETECTED 이벤트 수신."""
        role = (event.data or {}).get("role")
        if not role:
            return
        with self._lock:
            if self._role_reg is None:
                return
            if self._role_reg["detected_role"] is not None:
                return  # 이미 감지됨, 확인 대기 중
            self._role_reg["detected_role"] = role
            snapshot = self._snapshot()
        self._broadcast(snapshot)

    # ── HTTP 핸들러 (routes/players.py에서 호출) ───────────────────────────────

    def add_player(self, playername: str) -> dict:
        with self._lock:
            pid = self._pm.add_player(playername)
            snapshot = self._snapshot()
        self._broadcast(snapshot)
        return {"player_id": pid}

    def start_registration(self) -> dict:
        with self._lock:
            pid = self._pm.add_pending_player()
            self._pm.start_seat_registration(pid)
            self._phase = CommonPhase.SEAT_REGISTER
            self._seat_step = "right_pending"
            self._pending_register_id = pid
            snapshot = self._snapshot()
        self._push_context(CommonPhase.SEAT_REGISTER, active_player=pid)
        self._broadcast(snapshot)
        return {"player_id": pid}

    def finalize_player(self, player_id: str, playername: str) -> None:
        with self._lock:
            self._pm.edit_playername(player_id, playername)
            self._seat_step = "idle"
            if self._pending_register_id == player_id:
                self._pending_register_id = None
            snapshot = self._snapshot()
        self._notify_players()
        self._broadcast(snapshot)

    def edit_player(self, player_id: str, playername: str) -> None:
        with self._lock:
            self._pm.edit_playername(player_id, playername)
            snapshot = self._snapshot()
        self._notify_players()
        self._broadcast(snapshot)

    def remove_player(self, player_id: str) -> None:
        with self._lock:
            self._pm.remove_player(player_id)
            if self._pending_register_id == player_id:
                self._pending_register_id = None
            if self._pm.state.registering_player_id == player_id:
                self._pm.state.registering_player_id = None
                self._pm.state.pending_wrists = {}
            if (
                self._pm.state.registering_player_id is None
                and self._phase == CommonPhase.SEAT_REGISTER
            ):
                self._phase = CommonPhase.PLAYER_SETUP
                self._seat_step = "idle"
            snapshot = self._snapshot()
        if self._phase == CommonPhase.PLAYER_SETUP:
            self._push_context(CommonPhase.PLAYER_SETUP)
        self._notify_players()
        self._broadcast(snapshot)

    def get_players_list(self) -> list[dict]:
        with self._lock:
            return [p.to_dict() for p in self._pm.state.players]

    def cancel_seat_registration(self, player_id: str | None = None) -> None:
        with self._lock:
            target_id = player_id or self._pending_register_id or self._pm.state.registering_player_id
            self._pm.state.registering_player_id = None
            self._pm.state.pending_wrists = {}
            self._pending_register_id = None
            if self._phase == CommonPhase.SEAT_REGISTER:
                self._phase = CommonPhase.PLAYER_SETUP
                self._seat_step = "idle"
            if target_id:
                self._pm.state.players = [
                    player
                    for player in self._pm.state.players
                    if not (
                        player.player_id == target_id
                        and not player.playername
                        and player.seat_zone is None
                    )
                ]
            snapshot = self._snapshot()
        self._push_context(CommonPhase.PLAYER_SETUP)
        self._notify_players()
        self._broadcast(snapshot)

    def start_seat_registration(self, player_id: str) -> None:
        with self._lock:
            self._pm.restart_seat_registration(player_id)
            self._phase = CommonPhase.SEAT_REGISTER
            self._seat_step = "right_pending"
            snapshot = self._snapshot()
        self._push_context(CommonPhase.SEAT_REGISTER, active_player=player_id)
        self._notify_players()
        self._broadcast(snapshot)

    def start_werewolf_game(
        self, player_roles: list[dict], center_roles: list[str]
    ) -> None:
        """역할 배정 완료 후 WerewolfFSM을 생성하고 게임을 시작한다."""
        ws_players = [
            WerewolfPlayerState(
                player_id=r["player_id"],
                original_role=r["role"],
                current_role=r["role"],
            )
            for r in player_roles
        ]

        with self._lock:
            self._werewolf_fsm = WerewolfFSM(
                players=ws_players,
                center_cards=center_roles,
                broadcast=self._ww_broadcast,
            )
            self._werewolf_fsm.start()
            snapshot = self._snapshot()

        self._broadcast(snapshot)

    def current_snapshot(self) -> dict:
        with self._lock:
            return self._snapshot()

    # ── WebSocket input 처리 ───────────────────────────────────────────────────

    def handle_input(self, input_type: str, data: dict, player_id: str | None = None) -> None:
        if input_type == "start_registration":
            self.start_registration()
        elif input_type == "finalize_player":
            pid = data.get("player_id")
            name = data.get("playername", "")
            if pid and name:
                self.finalize_player(pid, name)
        elif input_type == "start_seat_registration":
            pid = data.get("player_id")
            if pid:
                self.start_seat_registration(pid)
        elif input_type == "cancel_seat_registration":
            self.cancel_seat_registration(data.get("player_id"))
        elif input_type == "player_add":
            name = data.get("playername", "")
            if name:
                self.add_player(name)
        elif input_type == "player_edit":
            pid = data.get("player_id")
            name = data.get("playername", "")
            if pid and name:
                self.edit_player(pid, name)
        elif input_type == "player_remove":
            pid = data.get("player_id")
            if pid:
                self.remove_player(pid)
        elif input_type == "select_game":
            game_type = data.get("game_type", "")
            self._handle_select_game(game_type)
        elif input_type == "start_role_registration":
            selected_roles = data.get("selected_roles", [])
            player_order = data.get("player_order", [])
            if selected_roles and player_order:
                self.start_role_registration(selected_roles, player_order)
        elif input_type == "confirm_role":
            pid = data.get("player_id")
            if pid:
                self.confirm_role(pid)
        elif input_type == "start_werewolf_game":
            player_roles = data.get("player_roles", [])
            center_roles = data.get("center_roles", [])
            if player_roles:
                self.start_werewolf_game(player_roles, center_roles)
        elif input_type == "reset_game":
            with self._lock:
                self._werewolf_fsm = None
                snapshot = self._snapshot()
            self._broadcast(snapshot)
        elif input_type in (
            WerewolfInputType.ADD_30_SEC,
            WerewolfInputType.START_NOW,
            WerewolfInputType.VOTE_PLAYER,
        ):
            self._handle_werewolf_input(input_type, data, player_id)

    # ── 게임 선택 & 역할 등록 ────────────────────────────────────────────────────

    def _handle_select_game(self, game_type: str) -> None:
        """로비에서 게임 선택. 현재는 phase 기록만."""
        with self._lock:
            self._phase = CommonPhase.GAME_SELECT
            snapshot = self._snapshot()
        self._broadcast(snapshot)

    def start_role_registration(
        self,
        selected_roles: list[str],
        player_order: list[str],
    ) -> None:
        """역할 카드를 선택하고 역할 등록 단계 진입.

        selected_roles: 프론트에서 선택한 역할 id 목록 (werewolf_1, mason_2 등 포함, 플레이어 수+3장)
        player_order:   등록 순서대로 정렬된 player_id 목록
        """
        if not player_order:
            return
        normalized_roles = [_normalize_role(r) for r in selected_roles]
        first_player = player_order[0]

        with self._lock:
            self._phase = _PHASE_ROLE_REGISTRATION
            self._role_reg = {
                "all_roles": normalized_roles,
                "player_order": player_order,
                "player_index": 0,
                "player_id": first_player,
                "detected_role": None,
                "confirmed_roles": {},
            }
            snapshot = self._snapshot()

        self._push_role_reg_context(first_player)
        self._broadcast(snapshot)

    def confirm_role(self, player_id: str) -> None:
        """플레이어가 감지된 역할을 확인. 다음 플레이어로 이동하거나 게임 시작."""
        with self._lock:
            if self._role_reg is None:
                return
            detected = self._role_reg.get("detected_role")
            if detected is None:
                return

            self._role_reg["confirmed_roles"][player_id] = detected
            next_index = self._role_reg["player_index"] + 1
            player_order = self._role_reg["player_order"]

            if next_index < len(player_order):
                # 다음 플레이어
                next_player = player_order[next_index]
                self._role_reg["player_index"] = next_index
                self._role_reg["player_id"] = next_player
                self._role_reg["detected_role"] = None
                snapshot = self._snapshot()
                start_game = False
            else:
                # 모든 플레이어 완료 → 센터 카드 계산 후 게임 시작
                confirmed_roles = dict(self._role_reg["confirmed_roles"])
                all_roles = list(self._role_reg["all_roles"])
                for role in confirmed_roles.values():
                    if role in all_roles:
                        all_roles.remove(role)
                center_cards = all_roles[:3]

                players_data = [
                    {"player_id": pid, "role": confirmed_roles[pid]}
                    for pid in player_order
                ]
                self._role_reg = None
                snapshot = None
                start_game = True

        if start_game:
            self.start_werewolf_game(players_data, center_cards)
        else:
            self._push_role_reg_context(next_player)
            self._broadcast(snapshot)

    def _push_role_reg_context(self, player_id: str) -> None:
        """역할 등록 단계 FusionContext 발송 — 해당 플레이어의 카드 감지 대기."""
        self._state_version += 1
        ctx = FusionContext(
            fsm_state=_PHASE_ROLE_REGISTRATION,
            game_type="werewolf",
            active_player=player_id,
            allowed_actors=[player_id],
            expected_events=[WerewolfEventType.ROLE_DETECTED],
            reject_events=[
                WerewolfEventType.CARD_PEEK,
                WerewolfEventType.CARD_SWAP,
                WerewolfEventType.VOTE_POINT,
            ],
            valid_targets=None,
            zones={},
            anchors={},
            params={"stabilization_frames": 5},
        )
        self._send_fusion_context(ctx, self._state_version)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _snapshot(self, sound: str | None = None) -> dict:
        registering = self._pending_register_id or self._pm.state.registering_player_id
        game_state = (
            self._werewolf_fsm.get_state_dict()
            if self._werewolf_fsm is not None
            else None
        )
        return build_state_snapshot(
            players=self._pm.state.players,
            phase=self._phase,
            registering_player_id=registering,
            seat_step=self._seat_step,
            sound=sound,
            game_state=game_state,
            gesture_confirmed=self._gesture_confirmed,
        )

    def _push_context(self, phase: str, active_player: str | None = None) -> None:
        self._state_version += 1
        if phase == CommonPhase.SEAT_REGISTER:
            expected = [
                CommonEventType.SEAT_RIGHT_REGISTERED,
                CommonEventType.SEAT_REGISTERED,
            ]
            allowed = [active_player] if active_player else []
        elif phase == CommonPhase.PLAYER_SETUP:
            expected = [CommonEventType.GESTURE_CONFIRMED]
            # allowed_actors 비워두면 모든 플레이어 허용 (개발 모드 fallback)
            allowed = []
        else:
            expected = []
            allowed = [active_player] if active_player else []
        ctx = FusionContext(
            fsm_state=phase,
            game_type=None,
            active_player=active_player,
            allowed_actors=allowed,
            expected_events=expected,
            params={"gesture_stabilization_frames": 3}
            if phase == CommonPhase.SEAT_REGISTER
            else {},
        )
        self._send_fusion_context(ctx, self._state_version)

    # ── 늑대인간 게임 ──────────────────────────────────────────────────────────

    async def _ww_broadcast(self, _msg: WSMessage) -> None:
        """FSM 타이머가 asyncio 루프에서 직접 호출하는 broadcast 콜백."""
        with self._lock:
            snapshot = self._snapshot()
        cb = self._broadcast_cb
        if cb is not None:
            result = cb(snapshot)
            if asyncio.iscoroutine(result):
                await result

    def _handle_gesture_confirmed(self, event: GameEvent) -> None:
        """OK 사인 감지 → player_id를 one-shot으로 broadcast."""
        actor_id = event.actor_id
        if not actor_id:
            return
        with self._lock:
            self._gesture_confirmed = actor_id
            snapshot = self._snapshot()
            self._gesture_confirmed = None
        self._broadcast(snapshot)

    def _handle_werewolf_event(self, event: GameEvent) -> None:
        with self._lock:
            if self._werewolf_fsm is None:
                return
            self._werewolf_fsm.handle_event(event)
            snapshot = self._snapshot()
        self._broadcast(snapshot)

    def _handle_werewolf_input(self, input_type: str, data: dict, player_id: str | None) -> None:
        with self._lock:
            if self._werewolf_fsm is None:
                return
            self._werewolf_fsm.handle_input(input_type, data, player_id)
            snapshot = self._snapshot()
        self._broadcast(snapshot)

    def _broadcast(self, snapshot: dict) -> None:
        if self._broadcast_cb is None or self._loop is None:
            return
        cb = self._broadcast_cb
        asyncio.run_coroutine_threadsafe(_call_async(cb, snapshot), self._loop)


async def _call_async(cb: Callable[[dict], None], snapshot: dict) -> None:
    result = cb(snapshot)
    if asyncio.iscoroutine(result):
        await result
