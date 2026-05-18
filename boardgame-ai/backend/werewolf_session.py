"""WerewolfFSM을 WebSocket 클라이언트 방식으로 구동하는 세션."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from core.constants import MsgType
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from games.werewolf.fsm import WerewolfFSM
from games.werewolf.ontology import WerewolfEventType, WerewolfInputType
from games.werewolf.state import WerewolfPlayerState


def _normalize_role(role_id: str) -> str:
    return re.sub(r"_\d+$", "", role_id)


class WerewolfSession:
    def __init__(
        self,
        websocket: WebSocket,
        send_fusion_context_fn: Callable[[FusionContext, int], None],
        loop: asyncio.AbstractEventLoop,
        pipeline_switcher: Callable[[str | None], None] | None = None,
    ) -> None:
        self.websocket = websocket
        self._send_fusion_context = send_fusion_context_fn
        self._pipeline_switcher = pipeline_switcher
        self._loop = loop
        self._fsm: WerewolfFSM | None = None
        self._state_version: int = 0
        self._role_reg: dict | None = None

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    async def send_hello(self) -> None:
        await self.send(WSMessage.make_hello({"game_type": "werewolf"}))

    async def handle_client_message(self, data: dict[str, Any]) -> None:
        input_type = str(data.get("input_type", ""))
        payload = dict(data.get("data", {}))
        player_id = data.get("player_id")

        if input_type == "START_ROLE_REGISTRATION":
            await self._start_role_registration(payload)
            return

        if input_type == "CONFIRM_ROLE":
            await self._confirm_role(player_id, payload)
            return

        if input_type == "START_WEREWOLF_GAME":
            await self._start_game(payload)
            return

        if input_type == "RESTART":
            self._fsm = None
            self._role_reg = None
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
        first_player = player_order[0]
        self._role_reg = {
            "all_roles": normalized_roles,
            "player_order": player_order,
            "player_index": 0,
            "player_id": first_player,
            "detected_role": None,
            "confirmed_roles": {},
        }
        if self._pipeline_switcher is not None:
            self._pipeline_switcher("werewolf")
        await self._push_role_reg_context(first_player)
        await self._broadcast_role_reg()

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
            all_roles = list(self._role_reg["all_roles"])
            for role in confirmed.values():
                if role in all_roles:
                    all_roles.remove(role)
            center_cards = all_roles[:3]
            players_data = [
                {"player_id": pid, "role": confirmed[pid]}
                for pid in player_order
            ]
            self._role_reg = None
            await self._start_game({"players": players_data, "center_cards": center_cards})

    async def _start_game(self, payload: dict) -> None:
        players_data = payload.get("players", [])
        center_cards = payload.get("center_cards", [])
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

    async def _broadcast_role_reg(self) -> None:
        self._state_version += 1
        await self.send(WSMessage(
            msg_type=MsgType.STATE_UPDATE.value,
            payload={"phase": "role_registration", "role_reg": dict(self._role_reg or {})},
            state_version=self._state_version,
        ))

    async def _broadcast_msg(self, msg: WSMessage) -> None:
        """WerewolfFSM 타이머가 호출하는 broadcast 콜백."""
        try:
            await self.send_many([msg])
        except Exception:
            pass  # disconnect 후 타이머가 남아 있을 때 조용히 종료

    async def send_many(self, messages: list[WSMessage]) -> None:
        for msg in messages:
            if msg.msg_type == MsgType.FUSION_CONTEXT.value:
                ctx = FusionContext.from_dict(msg.payload)
                self._send_fusion_context(ctx, msg.state_version)
            else:
                await self.send(msg)

    async def send(self, message: WSMessage) -> None:
        await self.websocket.send_json(message.to_dict())
