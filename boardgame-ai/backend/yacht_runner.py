"""YachtVisionPipeline 실행 어댑터 + 비전 이벤트 → 활성 YachtSession 라우터.

비전 파이프라인이 LocalBridge에 발화한 yacht GameEvent를 활성 YachtSession.fsm으로
전달한다. 단일 활성 세션 가정 (멀티 세션은 future work).

스레드 안전:
  - 비전 daemon thread → asyncio.run_coroutine_threadsafe로 asyncio loop에 marshal
  - 활성 세션 레지스트리는 threading.Lock으로 보호
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import queue
import threading
from pathlib import Path
from typing import Protocol

from bridge.local_bridge import LocalBridge
from core.events import GameEvent
from games.yacht import YachtEventType
from vision.yacht.config import VisionConfig
from vision.yacht.pipeline import VisionPipeline

logger = logging.getLogger(__name__)

_YACHT_EVENT_TYPES = {
    YachtEventType.ROLL_CONFIRMED.value,
    YachtEventType.ROLL_UNREADABLE.value,
    YachtEventType.DICE_ESCAPED.value,
    YachtEventType.RULE_VIOLATION.value,
    YachtEventType.RULE_VIOLATION_LOWER.value,
}


class _YachtSessionLike(Protocol):
    """순환 import 회피용 — 라우팅에 필요한 최소 인터페이스."""

    fsm: object | None

    async def dispatch_vision_event(self, event: GameEvent) -> None: ...


class YachtRunner:
    """VisionPipeline 실행 + LocalBridge → YachtSession 이벤트 라우터.

    server.py lifespan에서 인스턴스화하여 app.state에 보관.
    /ws/yacht 연결 시 register_session(), 끊김 시 deregister_session() 호출.
    """

    def __init__(
        self,
        config: VisionConfig,
        bridge: LocalBridge,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._config = config
        self._bridge = bridge
        self._loop = loop
        self._pipeline: VisionPipeline | None = None
        self._thread: threading.Thread | None = None
        self._active_session: _YachtSessionLike | None = None
        self._session_lock = threading.Lock()
        bridge.on_game_event(self._route_event)

    # ── VisionPipeline 실행 ───────────────────────────────────────────────────

    def start(self, frame_queue: "queue.Queue") -> None:
        weights = Path(self._config.weights_path)
        if not weights.exists():
            print(
                f"[yacht_runner] 가중치 파일 없음: {weights} — "
                "비전 파이프라인 없이 백엔드만 시작합니다."
            )
            return
        self._pipeline = VisionPipeline(
            config=self._config,
            bridge=self._bridge,
            players=[],
        )
        self._thread = threading.Thread(
            target=self._pipeline.start,
            args=(frame_queue,),
            daemon=True,
            name="yacht-vision-pipeline",
        )
        self._thread.start()
        print(f"[yacht_runner] 요트 비전 파이프라인 시작 (weights={weights})")

    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()

    def set_active(self, enabled: bool) -> None:
        if self._pipeline is not None:
            self._pipeline.set_active(enabled)

    def update_players(self, players: list) -> None:
        if self._pipeline is not None:
            self._pipeline.update_players(players)

    # ── 세션 레지스트리 ───────────────────────────────────────────────────────

    def register_session(self, session: _YachtSessionLike) -> None:
        with self._session_lock:
            self._active_session = session

    def deregister_session(self, session: _YachtSessionLike) -> None:
        with self._session_lock:
            if self._active_session is session:
                self._active_session = None

    # ── 이벤트 라우팅 ─────────────────────────────────────────────────────────

    def _route_event(self, event: GameEvent, _state_version: int) -> None:
        if event.event_type not in _YACHT_EVENT_TYPES:
            return
        with self._session_lock:
            session = self._active_session
        if session is None or session.fsm is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            session.dispatch_vision_event(event),
            self._loop,
        )
        future.add_done_callback(
            lambda f, etype=event.event_type: _log_dispatch_failure(f, etype)
        )


def _log_dispatch_failure(future: concurrent.futures.Future[None], event_type: str) -> None:
    try:
        future.result()
    except concurrent.futures.CancelledError:
        return
    except Exception:
        logger.exception("dispatch_vision_event failed (event_type=%s)", event_type)
