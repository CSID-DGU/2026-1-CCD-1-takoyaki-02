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
from core.events import FusionContext, GameEvent
from core.models import SeatZone
from core.player_manager import PlayerManager
from games.werewolf.fsm import WerewolfFSM
from games.werewolf.state import WerewolfPlayerState


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
        # 등록 흐름 상의 player_id (record_seat 후 PlayerManager.registering_player_id가
        # 비워져도 finalize/cancel 전까지 프론트가 모달을 유지하도록 별도 추적).
        self._pending_register_id: str | None = None
        # PlayerManager 변경 시 비전 파이프라인에 새 players 리스트 전달용 콜백.
        # 좌석 등록 완료 / 플레이어 추가·삭제·이름수정 직후마다 호출.
        self._players_listener: Callable[[list], None] | None = None
        self._werewolf_fsm: WerewolfFSM | None = None

    def set_broadcast(
        self,
        cb: Callable[[dict], None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._broadcast_cb = cb
        self._loop = loop

    def set_players_listener(self, cb: Callable[[list], None]) -> None:
        """PlayerManager 변경 시 비전 파이프라인 등 외부 컴포넌트에 전달할 콜백 등록.

        콜백 인자: 현재 등록된(또는 전체) Player 리스트.
        """
        self._players_listener = cb

    def _notify_players(self) -> None:
        """좌석 등록 완료/삭제/수정 직후 비전 파이프라인에 새 players 전달.

        seat_zone이 채워진 플레이어만 매칭 후보로 의미가 있으므로 필터링.
        호출자는 이미 self._lock을 잡고 있다고 가정하지 않음 (스냅샷만 읽음).
        """
        if self._players_listener is None:
            return
        registered = [p for p in self._pm.state.players if p.seat_zone is not None]
        # 비전 스레드 갱신 실패가 백엔드 흐름을 끊지 않도록 흡수
        with contextlib.suppress(Exception):
            self._players_listener(registered)

    # ── 비전 이벤트 소비 ───────────────────────────────────────────────────────

    def handle_game_event(self, event: GameEvent, _state_version: int) -> None:
        if event.event_type == CommonEventType.SEAT_RIGHT_REGISTERED:
            self._handle_seat_right_registered(event)
        elif event.event_type == CommonEventType.SEAT_REGISTERED:
            self._handle_seat_registered(event)

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

        # 비전에는 다시 PLAYER_SETUP phase로 알림 (등록 종료)
        self._push_context(CommonPhase.PLAYER_SETUP)
        # 좌석 등록 완료 → 비전 파이프라인의 players 리스트 갱신
        self._notify_players()
        self._broadcast(snapshot)

    # ── HTTP 핸들러 (routes/players.py에서 호출) ───────────────────────────────

    def add_player(self, playername: str) -> dict:
        with self._lock:
            pid = self._pm.add_player(playername)
            snapshot = self._snapshot()
        self._broadcast(snapshot)
        return {"player_id": pid}

    def start_registration(self) -> dict:
        """임시 player_id 발급 + 즉시 좌석 등록 phase 진입.

        프론트가 "+" 버튼 누르면 호출. 이름은 등록 완료 후 finalize로 받음.
        """
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
        """등록 완료 후 이름 확정."""
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
            # 등록 도중/완료 후 취소된 경우 모든 등록 상태 복귀
            if self._pending_register_id == player_id:
                self._pending_register_id = None
            if (
                self._pm.state.registering_player_id is None
                and self._phase == CommonPhase.SEAT_REGISTER
            ):
                self._phase = CommonPhase.PLAYER_SETUP
                self._seat_step = "idle"
            snapshot = self._snapshot()
        # 등록 phase 빠져나갔으면 비전에도 알림
        if self._phase == CommonPhase.PLAYER_SETUP:
            self._push_context(CommonPhase.PLAYER_SETUP)
        self._notify_players()
        self._broadcast(snapshot)

    def get_players_list(self) -> list[dict]:
        with self._lock:
            return [p.to_dict() for p in self._pm.state.players]

    def cancel_seat_registration(self) -> None:
        """등록 모달 "취소" 처리 — 좌석 등록만 중단하고 플레이어는 유지.

        임시 등록(이름 없음) 중인 경우 호출자가 player_remove로 직접 삭제.
        기존 플레이어 재등록 중에는 이 함수를 사용해 플레이어 보존.
        """
        with self._lock:
            self._pm.state.registering_player_id = None
            self._pm.state.pending_wrists = {}
            self._pending_register_id = None
            if self._phase == CommonPhase.SEAT_REGISTER:
                self._phase = CommonPhase.PLAYER_SETUP
                self._seat_step = "idle"
            snapshot = self._snapshot()
        self._push_context(CommonPhase.PLAYER_SETUP)
        self._broadcast(snapshot)

    def start_seat_registration(self, player_id: str) -> None:
        """기존 플레이어의 좌석 재등록 (seat_zone 초기화 → 비전 후보에서 일시 제외)."""
        with self._lock:
            self._pm.restart_seat_registration(player_id)
            self._phase = CommonPhase.SEAT_REGISTER
            self._seat_step = "right_pending"
            snapshot = self._snapshot()
        self._push_context(CommonPhase.SEAT_REGISTER, active_player=player_id)
        # seat_zone=None이 되었으므로 매칭 후보 리스트도 즉시 갱신
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

        orch = self

        async def _fsm_broadcast(ws_msg) -> None:
            with orch._lock:
                snapshot = orch._snapshot()
            if orch._broadcast_cb:
                await orch._broadcast_cb(snapshot)

        with self._lock:
            self._werewolf_fsm = WerewolfFSM(
                players=ws_players,
                center_cards=center_roles,
                broadcast=_fsm_broadcast,
            )
            self._werewolf_fsm.start()
            snapshot = self._snapshot()

        self._broadcast(snapshot)

    def current_snapshot(self) -> dict:
        with self._lock:
            return self._snapshot()

    # ── WebSocket input 처리 ───────────────────────────────────────────────────

    def handle_input(self, input_type: str, data: dict) -> None:
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
            self.cancel_seat_registration()
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
        elif input_type in ("add_30_sec", "start_now", "werewolf_vote_player"):
            if self._werewolf_fsm is None:
                return
            voter_id = data.get("voter_id")
            with self._lock:
                msgs = self._werewolf_fsm.handle_input(
                    input_type, data, player_id=voter_id
                )
                snapshot = self._snapshot()
            if msgs:
                self._broadcast(snapshot)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _snapshot(self, sound: str | None = None) -> dict:
        # pending_register_id가 있으면 우선 사용 (record_seat 후 PM dict는 비워지지만
        # finalize 전까지 프론트가 모달을 유지해야 함)
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
        )

    def _push_context(self, phase: str, active_player: str | None = None) -> None:
        self._state_version += 1
        if phase == CommonPhase.SEAT_REGISTER:
            expected = [
                CommonEventType.SEAT_RIGHT_REGISTERED,
                CommonEventType.SEAT_REGISTERED,
            ]
        else:
            expected = []
        ctx = FusionContext(
            fsm_state=phase,
            game_type=None,
            active_player=active_player,
            allowed_actors=[active_player] if active_player else [],
            expected_events=expected,
        )
        self._send_fusion_context(ctx, self._state_version)

    def _broadcast(self, snapshot: dict) -> None:
        if self._broadcast_cb is None or self._loop is None:
            return
        cb = self._broadcast_cb
        asyncio.run_coroutine_threadsafe(_call_async(cb, snapshot), self._loop)


async def _call_async(cb: Callable[[dict], None], snapshot: dict) -> None:
    result = cb(snapshot)
    if asyncio.iscoroutine(result):
        await result
