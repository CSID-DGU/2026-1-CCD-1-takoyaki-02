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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players_router)


@app.websocket("/ws/tablet")
async def ws_tablet(websocket: WebSocket) -> None:
    await tablet_ws_handler(websocket, app.state.orchestrator)
