"""FastAPI 앱 진입점.

실행:
    uvicorn backend.server:app --host 127.0.0.1 --port 8000

비전 파이프라인은 startup 시 백그라운드 daemon 스레드로 시작.
LocalBridge로 같은 프로세스 내 orchestrator와 통신.
"""

from __future__ import annotations

import asyncio
import random
from copy import deepcopy
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.orchestrator import Orchestrator
from backend.routes.players import router as players_router
from backend.vision_runner import VisionRunner
from backend.werewolf_runner import WerewolfRunner
from backend.ws.tablet import manager as ws_manager
from backend.ws.tablet import tablet_ws_handler
from bridge.local_bridge import LocalBridge
from core.envelope import WSMessage
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtGameState, YachtInputType
from vision.config import VisionConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()

    bridge = LocalBridge()
    config = VisionConfig()

    orchestrator = Orchestrator(
        send_fusion_context_fn=bridge.send_fusion_context,
    )
    orchestrator.set_broadcast(ws_manager.broadcast, loop)
    bridge.on_game_event(orchestrator.handle_game_event)

    vision_runner = VisionRunner(config=config, bridge=bridge)
    werewolf_runner = WerewolfRunner(bridge=bridge)

    # 좌석 등록 완료/플레이어 변경 시 두 파이프라인에 동시 전달
    def _on_players_changed(players: list) -> None:
        vision_runner.update_players(players)
        werewolf_runner.update_players(players)

    orchestrator.set_players_listener(_on_players_changed)
    vision_runner.start()
    werewolf_runner.start()

    app.state.orchestrator = orchestrator
    app.state.vision_runner = vision_runner
    app.state.werewolf_runner = werewolf_runner

    yield

    vision_runner.stop()
    werewolf_runner.stop()


app = FastAPI(title="Boardgame AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/tablet")
async def ws_tablet(websocket: WebSocket) -> None:
    await tablet_ws_handler(websocket, app.state.orchestrator)


@app.websocket("/ws/yacht")
async def yacht_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session = YachtSession(websocket)
    await session.send_hello()

    try:
        while True:
            data = await websocket.receive_json()
            await session.handle_client_message(data)
    except WebSocketDisconnect:
        return


class YachtSession:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.fsm: YachtFSM | None = None
        self.undo_stack: list[YachtGameState] = []

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
            previous_state = deepcopy(self.fsm.state)
            dice_values = payload.get("dice_values") or self.roll_dice(
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
            if self.roll_was_recorded(previous_state):
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
            await self.send_many(self.fsm.handle_event(event))
            return

        if input_type in {
            YachtInputType.DICE_KEEP_SELECTED.value,
            YachtInputType.DICE_REROLL_REQUESTED.value,
            YachtInputType.RESOLVE_UNREADABLE_ROLL.value,
        }:
            await self.send_many(self.fsm.handle_input(input_type, payload, player_id))
            return

        if input_type == YachtInputType.SCORE_CATEGORY_SELECTED.value:
            previous_state = deepcopy(self.fsm.state)
            messages = self.fsm.handle_input(input_type, payload, player_id)
            if self.score_was_recorded(previous_state, payload.get("category")):
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
            await self.send_many(
                self.fsm.restore_state(
                    restored_state,
                    f"{player_name}님의 주사위 굴림을 되돌렸습니다.",
                )
            )
            return

        if input_type == "RESTART":
            players = [p.to_dict() for p in self.fsm.state.players]
            await self.start_game({"players": players})
            return

        await self.send(WSMessage.make_error("UNKNOWN_INPUT", f"알 수 없는 입력입니다: {input_type}"))

    async def start_game(self, payload: dict[str, Any]) -> None:
        players = normalize_players(payload.get("players"))
        self.fsm = YachtFSM(players)
        self.undo_stack = []
        await self.send_many(self.fsm.start())

    def roll_was_recorded(self, previous_state: YachtGameState) -> bool:
        if self.fsm is None:
            return False
        return self.fsm.state.roll_count > previous_state.roll_count

    def score_was_recorded(self, previous_state: YachtGameState, category: Any) -> bool:
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
    def roll_dice(
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


def normalize_players(players: Any) -> list[dict[str, str]]:
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
