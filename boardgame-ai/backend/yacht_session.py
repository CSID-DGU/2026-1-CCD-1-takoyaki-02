"""YachtFSM을 WebSocket 클라이언트 방식으로 구동하는 세션."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from core.envelope import WSMessage
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtInputType


class YachtSession:
    def __init__(
        self,
        websocket: WebSocket,
        pipeline_switcher: Callable[[str | None], None] | None = None,
    ) -> None:
        self.websocket = websocket
        self.fsm: YachtFSM | None = None
        self._pipeline_switcher = pipeline_switcher

    async def send_hello(self) -> None:
        await self.send(WSMessage.make_hello({"game_type": "yacht"}))

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
            dice_values = payload.get("dice_values") or self._roll_dice()
            event = GameEvent(
                event_type=YachtEventType.ROLL_CONFIRMED.value,
                actor_id=self.fsm.state.current_player.player_id,
                confidence=1.0,
                frame_id=-1,
                data={"dice_values": dice_values, "keep_mask": self.fsm.state.keep_mask},
            )
            await self.send_many(self.fsm.handle_event(event))
            return

        if input_type == "DICE_ESCAPED":
            event = GameEvent(
                event_type=YachtEventType.DICE_ESCAPED.value,
                actor_id=self.fsm.state.current_player.player_id,
                confidence=1.0,
                frame_id=-1,
                data={},
            )
            await self.send_many(self.fsm.handle_event(event))
            return

        if input_type in {
            YachtInputType.DICE_KEEP_SELECTED.value,
            YachtInputType.DICE_REROLL_REQUESTED.value,
            YachtInputType.SCORE_CATEGORY_SELECTED.value,
            YachtInputType.RESOLVE_UNREADABLE_ROLL.value,
        }:
            await self.send_many(self.fsm.handle_input(input_type, payload, player_id))
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
        self.fsm = YachtFSM(players)
        await self.send_many(self.fsm.start())

    @staticmethod
    def _roll_dice() -> list[int]:
        return [random.randint(1, 6) for _ in range(5)]

    async def send_many(self, messages: list[WSMessage]) -> None:
        for message in messages:
            await self.send(message)

    async def send(self, message: WSMessage) -> None:
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
