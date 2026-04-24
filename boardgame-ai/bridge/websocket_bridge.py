"""WebSocket 브릿지. Phase 1 후반 구현 예정.

태블릿 UI와 연동하는 WebSocket 기반 브릿지.
LocalBridge와 동일한 Bridge 인터페이스를 구현하므로 FSM/비전 코드 변경 없이 교체 가능.
"""

from __future__ import annotations

from collections.abc import Callable

from bridge.interface import Bridge
from core.events import FusionContext, GameEvent


class WebSocketBridge(Bridge):
    """WebSocket 기반 비전 ↔ FSM 브릿지. Phase 1 후반 구현 예정."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        raise NotImplementedError(
            "WebSocketBridge is not yet implemented. " "Use LocalBridge for Phase 0/1 development."
        )

    def send_game_event(self, event: GameEvent, state_version: int) -> None:
        raise NotImplementedError

    def send_fusion_context(self, context: FusionContext, state_version: int) -> None:
        raise NotImplementedError

    def on_game_event(self, handler: Callable[[GameEvent, int], None]) -> None:
        raise NotImplementedError

    def on_fusion_context(self, handler: Callable[[FusionContext, int], None]) -> None:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
