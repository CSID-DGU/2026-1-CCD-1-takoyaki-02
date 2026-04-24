"""인프로세스 브릿지 구현. 개발/테스트용."""

from __future__ import annotations

from collections.abc import Callable

from bridge.interface import Bridge
from core.events import FusionContext, GameEvent


class LocalBridge(Bridge):
    """같은 프로세스 내에서 비전과 FSM을 직접 연결하는 브릿지.

    핸들러 리스트를 유지하고 send 시 등록된 모든 핸들러를 순차 호출한다.
    """

    def __init__(self) -> None:
        self._game_event_handlers: list[Callable[[GameEvent, int], None]] = []
        self._fusion_context_handlers: list[Callable[[FusionContext, int], None]] = []
        self._running = False

    def send_game_event(self, event: GameEvent, state_version: int) -> None:
        for handler in self._game_event_handlers:
            handler(event, state_version)

    def send_fusion_context(self, context: FusionContext, state_version: int) -> None:
        for handler in self._fusion_context_handlers:
            handler(context, state_version)

    def on_game_event(self, handler: Callable[[GameEvent, int], None]) -> None:
        self._game_event_handlers.append(handler)

    def on_fusion_context(self, handler: Callable[[FusionContext, int], None]) -> None:
        self._fusion_context_handlers.append(handler)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
