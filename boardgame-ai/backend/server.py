<<<<<<< Updated upstream
"""FastAPI 앱 진입점.

실행:
    uvicorn backend.server:app --host 127.0.0.1 --port 8000

비전 파이프라인은 startup 시 백그라운드 daemon 스레드로 시작.
LocalBridge로 같은 프로세스 내 orchestrator와 통신.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.orchestrator import Orchestrator
from backend.routes.players import router as players_router
from backend.vision_runner import VisionRunner
from backend.ws.tablet import manager as ws_manager
from backend.ws.tablet import tablet_ws_handler
from bridge.local_bridge import LocalBridge
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
    # PlayerManager 변경 시 비전 파이프라인의 players 리스트 자동 갱신.
    # (좌석 등록 완료/이름 수정/삭제 직후 호출 — 매칭 후보 동기화용)
    orchestrator.set_players_listener(vision_runner.update_players)
    vision_runner.start()

    app.state.orchestrator = orchestrator
    app.state.vision_runner = vision_runner

    yield

    vision_runner.stop()


app = FastAPI(title="Boardgame AI Backend", lifespan=lifespan)
=======
"""FastAPI backend for the tablet UI."""

from __future__ import annotations

import random
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.envelope import WSMessage
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtInputType

app = FastAPI(title="BoardGame AI")
>>>>>>> Stashed changes

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
<<<<<<< Updated upstream
=======
    allow_credentials=True,
>>>>>>> Stashed changes
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< Updated upstream
app.include_router(players_router)


@app.websocket("/ws/tablet")
async def ws_tablet(websocket: WebSocket) -> None:
    await tablet_ws_handler(websocket, app.state.orchestrator)
=======

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
            dice_values = payload.get("dice_values") or self.roll_dice()
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
        players = normalize_players(payload.get("players"))
        self.fsm = YachtFSM(players)
        await self.send_many(self.fsm.start())

    @staticmethod
    def roll_dice() -> list[int]:
        return [random.randint(1, 6) for _ in range(5)]

    async def send_many(self, messages: list[WSMessage]) -> None:
        for message in messages:
            await self.send(message)

    async def send(self, message: WSMessage) -> None:
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
>>>>>>> Stashed changes
