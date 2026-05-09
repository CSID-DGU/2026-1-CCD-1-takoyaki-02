"""FastAPI 앱 진입점.

실행:
    uvicorn backend.server:app --host 127.0.0.1 --port 8000

비전 파이프라인은 startup 시 백그라운드 daemon 스레드로 시작.
LocalBridge로 같은 프로세스 내 orchestrator와 통신.
"""

from __future__ import annotations

import asyncio
import random
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.lobby_runner import LobbyRunner
from backend.orchestrator import Orchestrator
from backend.routes.players import router as players_router
from backend.vision_runner import VisionRunner
from backend.werewolf_runner import WerewolfRunner
from backend.ws.tablet import manager as ws_manager
from backend.ws.tablet import tablet_ws_handler
from backend.yacht_runner import YachtRunner
from bridge.local_bridge import LocalBridge
from core.envelope import WSMessage
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtInputType
from vision.camera import CameraManager
from vision.yacht.config import VisionConfig


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

    camera = CameraManager(source=0, resolution=(1920, 1080), fps=30)
    vision_runner = VisionRunner(config=config, bridge=bridge)
    werewolf_runner = WerewolfRunner(bridge=bridge)
    lobby_runner = LobbyRunner(bridge=bridge)
    # 비전 → 활성 YachtSession.fsm 라우터. LocalBridge에 자동 핸들러 등록됨.
    yacht_runner = YachtRunner(bridge=bridge, loop=loop)

    def _on_players_changed(players: list) -> None:
        vision_runner.update_players(players)
        werewolf_runner.update_players(players)
        lobby_runner.update_players(players)

    orchestrator.set_players_listener(_on_players_changed)

    yacht_queue = camera.subscribe()
    werewolf_queue = camera.subscribe()
    lobby_queue = camera.subscribe()

    camera.start()
    vision_runner.start(yacht_queue)
    werewolf_runner.start(werewolf_queue)
    lobby_runner.start(lobby_queue)

    app.state.orchestrator = orchestrator
    app.state.camera = camera
    app.state.vision_runner = vision_runner
    app.state.werewolf_runner = werewolf_runner
    app.state.lobby_runner = lobby_runner
    app.state.bridge = bridge
    app.state.yacht_runner = yacht_runner

    yield

    camera.stop()
    vision_runner.stop()
    werewolf_runner.stop()
    lobby_runner.stop()


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
    session = YachtSession(websocket=websocket, bridge=app.state.bridge)
    # 비전 → 활성 세션 라우팅 활성화. send_hello/receive loop 어디서 예외가 나도
    # finally에서 반드시 deregister 되도록 register 직후부터 try 진입.
    app.state.yacht_runner.register_session(session)
    try:
        await session.send_hello()
        while True:
            data = await websocket.receive_json()
            await session.handle_client_message(data)
    except WebSocketDisconnect:
        return
    finally:
        app.state.yacht_runner.deregister_session(session)


class YachtSession:
    def __init__(self, websocket: WebSocket, bridge: LocalBridge) -> None:
        self.websocket = websocket
        self.fsm: YachtFSM | None = None
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
            await self.send(
                WSMessage.make_error("GAME_NOT_STARTED", "요트다이스가 시작되지 않았습니다.")
            )
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
            with self._fsm_lock:
                messages = self.fsm.handle_event(event)
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
            YachtInputType.SCORE_CATEGORY_SELECTED.value,
            YachtInputType.RESOLVE_UNREADABLE_ROLL.value,
        }:
            with self._fsm_lock:
                messages = self.fsm.handle_input(input_type, payload, player_id)
            await self.send_many(messages)
            return

        if input_type == "RESTART":
            players = [p.to_dict() for p in self.fsm.state.players]
            await self.start_game({"players": players})
            return

        await self.send(
            WSMessage.make_error("UNKNOWN_INPUT", f"알 수 없는 입력입니다: {input_type}")
        )

    async def start_game(self, payload: dict[str, Any]) -> None:
        players = normalize_players(payload.get("players"))
        with self._fsm_lock:
            # on_fusion_context 콜백 주입 → FSM이 phase 전환마다 비전에도 직접 알림
            self.fsm = YachtFSM(
                players,
                on_fusion_context=self._bridge.send_fusion_context,
            )
            messages = self.fsm.start()
        await self.send_many(messages)

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
