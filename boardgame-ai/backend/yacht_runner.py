"""요트 게임 라우팅 + 활성 세션 레지스트리.

비전 파이프라인이 LocalBridge에 발화한 yacht GameEvent를 활성 YachtSession.fsm으로
전달한다. 단일 활성 세션 가정 (멀티 세션은 future work).

스레드 안전:
  - 비전 daemon thread → asyncio.run_coroutine_threadsafe로 asyncio loop에 marshal
  - 활성 세션 레지스트리는 threading.Lock으로 보호
"""

from __future__ import annotations

import asyncio
import threading
from typing import Protocol

from bridge.local_bridge import LocalBridge
from core.events import GameEvent
from games.yacht import YachtEventType

# 라우팅 대상 yacht event_type 화이트리스트.
# 비전이 직접 발화하는 ROLL_CONFIRMED/ROLL_UNREADABLE/DICE_ESCAPED + fusion engine이
# allowed_actors 검증 실패 시 만드는 RULE_VIOLATION까지 포함.
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
    """LocalBridge → YachtSession 라우터.

    server.py lifespan에서 인스턴스화하여 app.state에 보관.
    /ws/yacht 연결 시 register_session(), 끊김 시 deregister_session() 호출.
    """

    def __init__(self, bridge: LocalBridge, loop: asyncio.AbstractEventLoop) -> None:
        self._bridge = bridge
        self._loop = loop
        self._active_session: _YachtSessionLike | None = None
        self._lock = threading.Lock()
        bridge.on_game_event(self._route_event)

    def register_session(self, session: _YachtSessionLike) -> None:
        with self._lock:
            self._active_session = session

    def deregister_session(self, session: _YachtSessionLike) -> None:
        # 빠른 재연결 race 방지 — 동일 세션일 때만 비움
        with self._lock:
            if self._active_session is session:
                self._active_session = None

    def _route_event(self, event: GameEvent, _state_version: int) -> None:
        if event.event_type not in _YACHT_EVENT_TYPES:
            return
        with self._lock:
            session = self._active_session
        if session is None or session.fsm is None:
            return
        # 비전 daemon thread → asyncio loop으로 marshal (WebSocket send는 loop 전용)
        asyncio.run_coroutine_threadsafe(
            session.dispatch_vision_event(event),
            self._loop,
        )
