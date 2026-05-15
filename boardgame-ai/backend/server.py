"""FastAPI 앱 진입점.

실행:
    uvicorn backend.server:app --host 127.0.0.1 --port 8000

비전 파이프라인은 startup 시 백그라운드 daemon 스레드로 시작.
LocalBridge로 같은 프로세스 내 orchestrator와 통신.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audio.catalog import BGM_DIR, SFX_DIR, TTS_CACHE_DIR
from audio.manager import AudioManager
from audio.prewarm import prewarm_static
from audio.tts_engine import TTSEngine
from backend.lobby_runner import LobbyRunner
from backend.orchestrator import Orchestrator
from backend.routes.players import router as players_router
from backend.werewolf_runner import WerewolfRunner
from backend.werewolf_session import WerewolfSession
from backend.ws.tablet import manager as ws_manager
from backend.ws.tablet import tablet_ws_handler
from backend.yacht_runner import YachtRunner
from backend.yacht_session import YachtSession
from bridge.local_bridge import LocalBridge
from vision.camera import CameraManager
from vision.yacht.config import VisionConfig

logger = logging.getLogger(__name__)

# .env를 가장 먼저 로드해 GOOGLE_APPLICATION_CREDENTIALS가 TTSEngine 초기화 전에 반영되도록.
# 상대경로는 boardgame-ai 루트 기준으로 절대경로화.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if _creds and not Path(_creds).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_PROJECT_ROOT / _creds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

    # 오디오: TTSEngine + AudioManager 부팅, static 사전 합성
    tts_engine = TTSEngine()
    audio_manager = AudioManager(tts_engine)
    if tts_engine.is_available():
        stats = await prewarm_static(tts_engine)
        logger.info("audio prewarm_static: %s", stats)
    else:
        logger.warning("TTS engine not available — STATIC/SESSION 캐시 hit만 동작")

    bridge = LocalBridge()
    config = VisionConfig()

    orchestrator = Orchestrator(
        send_fusion_context_fn=bridge.send_fusion_context,
    )
    orchestrator.set_broadcast(ws_manager.broadcast, loop)
    orchestrator.set_audio_manager(audio_manager)
    bridge.on_game_event(orchestrator.handle_game_event)

    camera = CameraManager(source=0, resolution=(1920, 1080), fps=30)
    # 비전 → 활성 YachtSession.fsm 라우터. LocalBridge에 자동 핸들러 등록됨.
    yacht_runner = YachtRunner(config=config, bridge=bridge, loop=loop)
    werewolf_runner = WerewolfRunner(bridge=bridge)
    lobby_runner = LobbyRunner(bridge=bridge)

    def _on_players_changed(players: list) -> None:
        yacht_runner.update_players(players)
        werewolf_runner.update_players(players)
        lobby_runner.update_players(players)

    def _on_game_switch(game_type: str | None) -> None:
        lobby_runner.set_active(game_type is None)
        yacht_runner.set_active(game_type == "yacht")
        werewolf_runner.set_active(game_type == "werewolf")

    orchestrator.set_players_listener(_on_players_changed)
    orchestrator.set_pipeline_switcher(_on_game_switch)

    yacht_queue = camera.subscribe()
    werewolf_queue = camera.subscribe()
    lobby_queue = camera.subscribe()

    camera.start()
    yacht_runner.start(yacht_queue)
    werewolf_runner.start(werewolf_queue)
    lobby_runner.start(lobby_queue)

    app.state.orchestrator = orchestrator
    app.state.bridge = bridge
    app.state.camera = camera
    app.state.yacht_runner = yacht_runner
    app.state.werewolf_runner = werewolf_runner
    app.state.lobby_runner = lobby_runner
    app.state.pipeline_switcher = _on_game_switch
    app.state.loop = loop
    app.state.audio_manager = audio_manager
    app.state.tts_engine = tts_engine

    yield

    camera.stop()
    yacht_runner.stop()
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

# 오디오 자산 정적 마운트 — frontend가 audio_url로 접근.
# 디렉토리가 없으면 StaticFiles가 에러내므로 미리 보장.
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/cache/tts", StaticFiles(directory=str(TTS_CACHE_DIR)), name="tts_cache")
app.mount("/sfx", StaticFiles(directory=str(SFX_DIR)), name="sfx")
app.mount("/bgm", StaticFiles(directory=str(BGM_DIR)), name="bgm")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── 오디오 디버그 엔드포인트 ────────────────────────────────────────────────────
# 시스템 검증용. 게임 FSM이 사운드 트리거를 박기 전이라도 BGM/SFX/TTS가
# 정상 작동하는지 확인할 수 있다. 브라우저에서 좌석 등록 → 게임 페이지(yacht)
# 진입 후, 다른 탭에서 아래 URL 한 번씩 호출하면 태블릿 브라우저에서 들림.

# stop은 /bgm/{name}보다 먼저 정의해야 정적 경로가 우선 매칭됨.
@app.post("/debug/audio/bgm-stop")
async def debug_bgm_stop() -> dict[str, str]:
    """BGM 정지."""
    await app.state.audio_manager.stop_bgm()
    return {"status": "stopped"}


@app.post("/debug/audio/bgm/{name}")
async def debug_bgm_play(name: str) -> dict[str, str]:
    """BGM 시작. name = 'lobby_loop' | 'game_outro' (catalog.BGM_REGISTRY 키)."""
    await app.state.audio_manager.play_bgm(name)
    return {"status": "ok", "bgm": name}


@app.post("/debug/audio/sfx/{name}")
async def debug_sfx_play(name: str) -> dict[str, str]:
    """SFX 재생. name = catalog.SFX_REGISTRY 키 (hand_register/dice_roll/...)."""
    pbid = await app.state.audio_manager.enqueue_sfx(name)
    return {"status": "ok", "sfx": name, "playback_id": pbid}


@app.post("/debug/audio/tts")
async def debug_tts(text: str = "안녕하세요. 오디오 시스템 테스트입니다.") -> dict[str, str]:
    """임의 문장 TTS 합성·재생. ?text= 쿼리로 문장 지정."""
    pbid = await app.state.audio_manager.enqueue_tts(text=text)
    return {"status": "ok", "text": text, "playback_id": pbid}


@app.post("/debug/audio/scenario")
async def debug_audio_scenario() -> dict[str, list[str]]:
    """엔드투엔드 시나리오: BGM 시작 → SFX → TTS → CRITICAL 인터럽트.

    실제 게임 흐름을 흉내 — TTS 재생 중 CRITICAL이 들어와 fade-out되는지
    체감으로 확인 가능. 합성·네트워크 지연 고려해 충분히 기다린 후 인터럽트.
    """
    from core.audio import AudioPriority

    mgr = app.state.audio_manager
    log: list[str] = []
    await mgr.stop_bgm()  # 이전 시나리오 잔재 정리
    log.append("BGM 정지 (이전 잔재 정리)")
    await mgr.play_bgm("lobby_loop")
    log.append("BGM 시작 (lobby_loop)")
    await mgr.enqueue_sfx("hand_register", priority=AudioPriority.HIGH)
    log.append("SFX (hand_register)")
    await mgr.enqueue_tts(
        text="이것은 오디오 시스템 검증을 위한 일반 멘트입니다. 잠시 후 긴급 알림이 끼어듭니다.",
    )
    log.append("TTS (long)")
    # 합성·다운로드·재생 시작 지연 + 충분한 청취 시간 확보. 4초 후 인터럽트.
    import asyncio as _asyncio
    await _asyncio.sleep(4.0)
    await mgr.enqueue_tts(
        text="긴급 알림입니다.",
        priority=AudioPriority.CRITICAL,
    )
    log.append("CRITICAL TTS (현재 멘트 인터럽트되어야 함)")
    return {"steps": log}


@app.websocket("/ws/tablet")
async def ws_tablet(websocket: WebSocket) -> None:
    await tablet_ws_handler(websocket, app.state.orchestrator)


@app.websocket("/ws/yacht")
async def yacht_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session = YachtSession(
        websocket=websocket,
        pipeline_switcher=app.state.pipeline_switcher,
        bridge=app.state.bridge,
        audio_manager=app.state.audio_manager,
    )
    # 비전 → 활성 세션 라우팅 활성화. send_hello/receive loop 어디서 예외가 나도
    # finally에서 반드시 deregister 되도록 register 직후부터 try 진입.
    app.state.yacht_runner.register_session(session)
    try:
        await session.send_hello()
        while True:
            data = await websocket.receive_json()
            await session.handle_client_message(data)
    except WebSocketDisconnect:
        app.state.pipeline_switcher(None)
    finally:
        app.state.yacht_runner.deregister_session(session)
        # 오디오 큐 정리 — 끊긴 세션이 ack 못 보내므로 _current가 stuck되는 것 방지.
        app.state.audio_manager.detach_broadcast()


@app.websocket("/ws/werewolf")
async def werewolf_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session = WerewolfSession(
        websocket=websocket,
        send_fusion_context_fn=app.state.bridge.send_fusion_context,
        loop=app.state.loop,
        pipeline_switcher=app.state.pipeline_switcher,
        audio_manager=app.state.audio_manager,
    )
    app.state.orchestrator.set_werewolf_event_handler(session.get_vision_event_handler())
    await session.send_hello()
    try:
        while True:
            data = await websocket.receive_json()
            await session.handle_client_message(data)
    except WebSocketDisconnect:
        app.state.orchestrator.set_werewolf_event_handler(None)
        app.state.pipeline_switcher(None)
        app.state.audio_manager.detach_broadcast()
