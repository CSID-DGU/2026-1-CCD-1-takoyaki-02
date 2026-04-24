"""비전 ↔ FSM 통신 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from core.events import FusionContext, GameEvent


class Bridge(ABC):
    @abstractmethod
    def send_game_event(self, event: GameEvent, state_version: int) -> None: ...

    @abstractmethod
    def send_fusion_context(self, context: FusionContext, state_version: int) -> None: ...

    @abstractmethod
    def on_game_event(self, handler: Callable[[GameEvent, int], None]) -> None: ...

    @abstractmethod
    def on_fusion_context(self, handler: Callable[[FusionContext, int], None]) -> None: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...
