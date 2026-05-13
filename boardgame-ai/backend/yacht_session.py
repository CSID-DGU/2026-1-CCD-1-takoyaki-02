"""YachtFSM을 WebSocket 클라이언트 방식으로 구동하는 세션."""

from __future__ import annotations

import random
import threading
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from fastapi import WebSocket

from bridge.local_bridge import LocalBridge
from core.envelope import WSMessage
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtGameState, YachtInputType


class YachtSession:
    def __init__(
        self,
        websocket: WebSocket,
        pipeline_switcher: Callable[[str | None], None] | None = None,
        bridge: LocalBridge | None = None,
    ) -> None:
        self.websocket = websocket
        self.fsm: YachtFSM | None = None
        self.undo_stack: list[YachtGameState] = []
        self._pipeline_switcher = pipeline_switcher
        self._bridge = bridge
        # FSM 상태 변경 직렬화 — 비전 스레드와 WS 스레드가 동시에 호출 가능
        self._fsm_lock = threading.Lock()

    async def send_hello(self) -> None:
        await self.send(WSMessage.make_hello({"game_type": "yacht"}))

    async def dispatch_vision_event(self, event: GameEvent) -> None:
        """yacht_runner가 호출. 비전 이벤트를 FSM에 전달하고 응답을 클라이언트로."""
        if self.fsm is None:
            return
        with self._fsm_lock:
            messages = self.fsm.handle_event(event)
        await self.send_many(messages)

    async def handle_client_message(self, data: dict[str, Any]) -> None:
        input_type = str(data.get("input_type", ""))
        payload = dict(data.get("data", {}))
        player_id = data.get("player_id")

        if input_type == "START_YACHT":
            await self.start_game(payload)
            return

        if self.fsm is None:
            await self.send(WSMessage.make_error("GAME_NOT_STARTED", "요트다이스가 시작되지 않았습니다."))
            return

        if input_type == "ROLL_DICE":
            with self._fsm_lock:
                previous_state = deepcopy(self.fsm.state)
                dice_values = payload.get("dice_values") or self._roll_dice(
                    self.fsm.state.dice_values,
                    self.fsm.state.keep_mask,
                )
                event = GameEvent(
                    event_type=YachtEventType.ROLL_CONFIRMED.value,
                    actor_id=self.fsm.state.current_player.player_id,
                    confidence=1.0,
                    frame_id=-1,
                    data={"dice_values": dice_values, "keep_mask": self.fsm.state.keep_mask},
                )
                messages = self.fsm.handle_event(event)
                if self._roll_was_recorded(previous_state):
                    self.undo_stack.append(previous_state)
            await self.send_many(messages)
            return

        if input_type == "DICE_ESCAPED":
            event = GameEvent(
                event_type=YachtEventType.DICE_ESCAPED.value,
                actor_id=self.fsm.state.current_player.player_id,
                confidence=1.0,
                frame_id=-1,
                data={},
            )
            with self._fsm_lock:
                messages = self.fsm.handle_event(event)
            await self.send_many(messages)
            return

        if input_type in {
            YachtInputType.DICE_KEEP_SELECTED.value,
            YachtInputType.DICE_REROLL_REQUESTED.value,
            YachtInputType.RESOLVE_UNREADABLE_ROLL.value,
        }:
            with self._fsm_lock:
                messages = self.fsm.handle_input(input_type, payload, player_id)
            await self.send_many(messages)
            return

        if input_type == YachtInputType.SCORE_CATEGORY_SELECTED.value:
            with self._fsm_lock:
                previous_state = deepcopy(self.fsm.state)
                messages = self.fsm.handle_input(input_type, payload, player_id)
                if self._score_was_recorded(previous_state, payload.get("category")):
                    self.undo_stack = []
            await self.send_many(messages)
            return

        if input_type == "UNDO_ROUND":
            if not self.undo_stack:
                await self.send(
                    WSMessage.make_error(
                        "NO_UNDO_HISTORY",
                        "되돌릴 주사위 굴림이 없습니다.",
                        self.fsm.state.state_version,
                    )
                )
                return
            restored_state = self.undo_stack.pop()
            player_name = restored_state.current_player.playername
            with self._fsm_lock:
                messages = self.fsm.restore_state(
                    restored_state,
                    f"{player_name}님의 주사위 굴림을 되돌렸습니다.",
                )
            await self.send_many(messages)
            return

        if input_type == "RESTART":
            players = [p.to_dict() for p in self.fsm.state.players]
            await self.start_game({"players": players})
            return

        await self.send(WSMessage.make_error("UNKNOWN_INPUT", f"알 수 없는 입력입니다: {input_type}"))

    async def start_game(self, payload: dict[str, Any]) -> None:
        if self._pipeline_switcher is not None:
            self._pipeline_switcher("yacht")
        players = _normalize_players(payload.get("players"))
        with self._fsm_lock:
            self.undo_stack = []
            self.fsm = YachtFSM(
                players,
                on_fusion_context=self._bridge.send_fusion_context if self._bridge else None,
            )
            messages = self.fsm.start()
        await self.send_many(messages)

    def _roll_was_recorded(self, previous_state: YachtGameState) -> bool:
        if self.fsm is None:
            return False
        return self.fsm.state.roll_count > previous_state.roll_count

    def _score_was_recorded(self, previous_state: YachtGameState, category: Any) -> bool:
        if self.fsm is None or not category:
            return False
        category_key = str(category)
        if category_key in previous_state.current_player.scores:
            return False
        scorer_id = previous_state.current_player.player_id
        scorer = next(
            (player for player in self.fsm.state.players if player.player_id == scorer_id),
            None,
        )
        return scorer is not None and category_key in scorer.scores

    @staticmethod
    def _roll_dice(
        current_values: list[int | None] | None = None,
        keep_mask: list[bool] | None = None,
    ) -> list[int]:
        values = list(current_values or [])
        keep = list(keep_mask or [])
        return [
            int(values[index])
            if index < len(values) and index < len(keep) and keep[index] and values[index] is not None
            else random.randint(1, 6)
            for index in range(5)
        ]

    async def send_many(self, messages: list[WSMessage]) -> None:
        for message in messages:
            await self.send(message)

    async def send(self, message: WSMessage) -> None:
        if message.msg_type == "state_update":
            message.payload["can_undo"] = bool(self.undo_stack)
        await self.websocket.send_json(message.to_dict())


def _normalize_players(players: Any) -> list[dict[str, str]]:
    if not isinstance(players, list) or not players:
        return [
            {"player_id": "p1", "playername": "형승"},
            {"player_id": "p2", "playername": "병진"},
            {"player_id": "p3", "playername": "성민"},
        ]

    normalized: list[dict[str, str]] = []
    for index, player in enumerate(players, start=1):
        if isinstance(player, str):
            normalized.append({"player_id": f"p{index}", "playername": player})
            continue
        if not isinstance(player, dict):
            continue
        player_id = str(player.get("player_id") or player.get("id") or f"p{index}")
        name = str(player.get("playername") or player.get("name") or player_id)
        normalized.append({"player_id": player_id, "playername": name})

    return normalized or [
        {"player_id": "p1", "playername": "형승"},
        {"player_id": "p2", "playername": "병진"},
        {"player_id": "p3", "playername": "성민"},
    ]
