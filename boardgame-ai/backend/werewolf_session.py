"""WerewolfFSM을 WebSocket 클라이언트 방식으로 구동하는 세션."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from audio.manager import AudioManager
from core.constants import MsgType
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from games.werewolf.fsm import WerewolfFSM
from games.werewolf.ontology import WerewolfEventType, WerewolfInputType, WerewolfPhase
from games.werewolf.state import WerewolfPlayerState

from agents.context import AgentContext
from agents.orchestrator import AgentOrchestrator

# AudioManager가 가로채는 msg_type 집합. yacht_session.py와 동일.
_AUDIO_MSG_TYPES = {
    MsgType.TTS_PLAY.value,
    MsgType.TTS_INTERRUPT.value,
    MsgType.SFX_PLAY.value,
    MsgType.BGM_PLAY.value,
    MsgType.BGM_DUCK.value,
}


def _normalize_role(role_id: str) -> str:
    return re.sub(r"_\d+$", "", role_id)


class WerewolfSession:
    def __init__(
        self,
        websocket: WebSocket,
        send_fusion_context_fn: Callable[[FusionContext, int], None],
        loop: asyncio.AbstractEventLoop,
        pipeline_switcher: Callable[[str | None], None] | None = None,
        audio_manager: AudioManager | None = None,
        agent_orchestrator: AgentOrchestrator | None = None,
    ) -> None:
        self.websocket = websocket
        self._send_fusion_context = send_fusion_context_fn
        self._pipeline_switcher = pipeline_switcher
        self._loop = loop
        self._fsm: WerewolfFSM | None = None
        self._state_version: int = 0
        self._role_reg: dict | None = None
        self._pending_game_data: dict | None = None
        self._audio_manager = audio_manager
        self._agent = agent_orchestrator
        # 동일 객체 참조를 유지해야 detach_broadcast_if에서 is 비교가 가능.
        self._send_raw_bound = self._send_raw
        if audio_manager is not None:
            audio_manager.attach_broadcast(self._send_raw_bound, session_id=audio_manager.get_session_id())
        self._pending_role_reg: dict | None = None
        # 현재 플레이어 목록 (AgentContext 빌드용)
        self._players_snapshot: list[dict] = []

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    async def send_hello(self) -> None:
        await self.send(WSMessage.make_hello({"game_type": "werewolf"}))

    async def handle_client_message(self, data: dict[str, Any]) -> None:
        input_type = str(data.get("input_type", ""))
        payload = dict(data.get("data", {}))
        player_id = data.get("player_id")

        # frontend가 오디오 재생 끝/중단을 통보. AudioManager 큐 진행 트리거.
        if input_type == "audio_ack" and self._audio_manager is not None:
            pbid = str(payload.get("playback_id", ""))
            status = str(payload.get("status", ""))
            if pbid:
                await self._audio_manager.handle_ack(pbid, status)
            return

        if input_type == "SET_STRATEGY_COACHING":
            if self._agent is not None:
                self._agent.set_strategy_enabled(bool(payload.get("enabled", False)))
            return

        if input_type == "START_ROLE_REGISTRATION":
            await self._start_role_registration(payload)
            return

        if input_type == "CONFIRM_ROLE":
            await self._confirm_role(player_id, payload)
            return

        if input_type == "CARD_SETUP_DONE":
            await self._finish_card_setup()
            return

        if input_type == "TTS_REQUEST":
            text = payload.get("text", "")
            if text and self._audio_manager is not None:
                await self._audio_manager.enqueue_tts(text=text)
            return

        if input_type == "START_WEREWOLF_GAME":
            await self._start_game(payload)
            return

        if input_type == "RESTART":
            self._fsm = None
            self._role_reg = None
            self._pending_game_data = None
            self._pending_role_reg = None
            if self._pipeline_switcher is not None:
                self._pipeline_switcher(None)
            return

        if self._fsm is None:
            await self.send(WSMessage.make_error("GAME_NOT_STARTED", "한밤이 시작되지 않았습니다."))
            return

        if input_type in (
            WerewolfInputType.ADD_30_SEC,
            WerewolfInputType.START_NOW,
            WerewolfInputType.VOTE_PLAYER,
        ):
            await self.send_many(self._fsm.handle_input(input_type, payload, player_id))
            return

        await self.send(WSMessage.make_error("UNKNOWN_INPUT", f"알 수 없는 입력입니다: {input_type}"))

    def get_vision_event_handler(self) -> Callable[[GameEvent, int], None]:
        """비전 스레드에서 호출될 동기 핸들러 반환. 이벤트를 asyncio 루프에 스케줄."""
        def handler(event: GameEvent, state_version: int) -> None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._handle_vision_event(event), self._loop
                )
            except RuntimeError:
                pass  # 루프 종료 후 호출 시 무시
        return handler

    # ── 역할 등록 (pre-game) ──────────────────────────────────────────────────

    async def _start_role_registration(self, payload: dict) -> None:
        selected_roles = payload.get("selected_roles", [])
        player_order = payload.get("player_order", [])
        if not player_order:
            return
        normalized_roles = [_normalize_role(r) for r in selected_roles]
        # 역할 등록 전 카드 세팅 안내를 먼저 표시. CARD_SETUP_DONE 수신 후 실제 등록 시작.
        self._pending_role_reg = {
            "selected_roles": normalized_roles,
            "player_order": player_order,
        }
        if self._pipeline_switcher is not None:
            self._pipeline_switcher("werewolf")
        self._state_version += 1
        await self.send(WSMessage(
            msg_type=MsgType.STATE_UPDATE.value,
            payload={"phase": "card_setup", "all_roles": normalized_roles},
            state_version=self._state_version,
        ))

    async def _confirm_role(self, player_id: str | None, payload: dict | None = None) -> None:
        if self._role_reg is None or player_id is None:
            return
        # 프론트에서 수동 선택한 역할 우선, 없으면 비전 감지 결과 사용
        confirmed_role = (payload or {}).get("role") or self._role_reg.get("detected_role")
        if confirmed_role is None:
            return

        self._role_reg["confirmed_roles"][player_id] = confirmed_role
        next_index = self._role_reg["player_index"] + 1
        player_order = self._role_reg["player_order"]

        if next_index < len(player_order):
            next_player = player_order[next_index]
            self._role_reg["player_index"] = next_index
            self._role_reg["player_id"] = next_player
            self._role_reg["detected_role"] = None
            await self._push_role_reg_context(next_player)
            await self._broadcast_role_reg()
        else:
            confirmed = dict(self._role_reg["confirmed_roles"])
            all_roles_snapshot = list(self._role_reg["all_roles"])
            working = list(all_roles_snapshot)
            for role in confirmed.values():
                if role in working:
                    working.remove(role)
            center_cards = working[:3]
            players_data = [
                {"player_id": pid, "role": confirmed[pid]}
                for pid in player_order
            ]
            self._role_reg = None
            await self._start_game({
                "players": players_data,
                "center_cards": center_cards,
                "all_roles": all_roles_snapshot,
            })

    async def _start_game(self, payload: dict) -> None:
        players_data = payload.get("players", [])
        center_cards = payload.get("center_cards", [])
        self._players_snapshot = [
            {"player_id": p["player_id"], "playername": p.get("playername", p["player_id"])}
            for p in players_data
        ]
        ws_players = [
            WerewolfPlayerState(
                player_id=p["player_id"],
                original_role=p["role"],
                current_role=p["role"],
            )
            for p in players_data
        ]
        self._fsm = WerewolfFSM(
            players=ws_players,
            center_cards=center_cards,
            broadcast=self._broadcast_msg,
        )
        await self.send_many(self._fsm.start())

    # ── 비전 이벤트 처리 ──────────────────────────────────────────────────────

    async def _handle_vision_event(self, event: GameEvent) -> None:
        etype = event.event_type

        # 규칙 에이전트: FSM 처리 이전에 위반 감지
        if self._agent is not None:
            await self._agent.on_game_event(event)

        if etype == WerewolfEventType.ROLE_DETECTED:
            await self._handle_role_detected(event)
            return

        if self._fsm is None:
            return

        if etype in (
            WerewolfEventType.CARD_PEEK,
            WerewolfEventType.CARD_SWAP,
            WerewolfEventType.VOTE_POINT,
        ):
            await self.send_many(self._fsm.handle_event(event))

    async def _handle_role_detected(self, event: GameEvent) -> None:
        role = (event.data or {}).get("role")
        if not role or self._role_reg is None:
            return
        if self._role_reg["detected_role"] is not None:
            return
        self._role_reg["detected_role"] = role
        await self._broadcast_role_reg()

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    async def _push_role_reg_context(self, player_id: str) -> None:
        self._state_version += 1
        ctx = FusionContext(
            fsm_state="role_registration",
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
            params={"stabilization_frames": 1},
        )
        self._send_fusion_context(ctx, self._state_version)
        await self._notify_agent_state_change(ctx)

    async def _notify_agent_state_change(self, fusion_ctx: FusionContext) -> None:
        if self._agent is None:
            return
        import time as _time
        timeout = None
        if fusion_ctx.fsm_state == WerewolfPhase.DAY_DISCUSSION:
            timeout = 300.0
        agent_ctx = AgentContext(
            game_type="werewolf",
            fsm_state=fusion_ctx.fsm_state,
            active_player=fusion_ctx.active_player,
            players=self._players_snapshot,
            allowed_actors=list(fusion_ctx.allowed_actors),
            expected_events=list(fusion_ctx.expected_events),
            turn_start_time=_time.time(),
            turn_timeout=timeout,
        )
        await self._agent.on_state_change(agent_ctx, state_version=self._state_version)

    async def _finish_card_setup(self) -> None:
        # 역할 등록 완료 후 게임 시작 경로 (기존 START_WEREWOLF_GAME 등)
        if self._pending_game_data is not None:
            data = self._pending_game_data
            self._pending_game_data = None
            await self._start_game(data)
            return
        # CardSetupGuide 완료 → 역할 등록 시작
        if self._pending_role_reg is None:
            return
        data = self._pending_role_reg
        self._pending_role_reg = None
        selected_roles = data["selected_roles"]
        player_order = data["player_order"]
        first_player = player_order[0]
        self._role_reg = {
            "all_roles": selected_roles,
            "player_order": player_order,
            "player_index": 0,
            "player_id": first_player,
            "detected_role": None,
            "confirmed_roles": {},
        }
        await self._push_role_reg_context(first_player)
        await self._broadcast_role_reg()

    async def _broadcast_role_reg(self) -> None:
        self._state_version += 1
        await self.send(WSMessage(
            msg_type=MsgType.STATE_UPDATE.value,
            payload={"phase": "role_registration", "role_reg": dict(self._role_reg or {})},
            state_version=self._state_version,
        ))

    async def _broadcast_msg(self, msg: WSMessage) -> None:
        """WerewolfFSM 타이머가 호출하는 broadcast 콜백. audio 메시지도 여기서 흐를 수 있음."""
        try:
            await self.send_many([msg])
        except Exception:
            pass  # disconnect 후 타이머가 남아 있을 때 조용히 종료

    async def send_many(self, messages: list[WSMessage]) -> None:
        for msg in messages:
            if msg.msg_type == MsgType.FUSION_CONTEXT.value:
                ctx = FusionContext.from_dict(msg.payload)
                self._send_fusion_context(ctx, msg.state_version)
                await self._notify_agent_state_change(ctx)
            else:
                await self.send(msg)

    async def send(self, message: WSMessage) -> None:
        """audio 메시지면 AudioManager 거쳐 audio_url 채운 후 broadcast."""
        if message.msg_type in _AUDIO_MSG_TYPES and self._audio_manager is not None:
            await self._audio_manager.handle_outbound(message)
            return
        await self._send_raw(message)

    async def _send_raw(self, message: WSMessage) -> None:
        await self.websocket.send_json(message.to_dict())
