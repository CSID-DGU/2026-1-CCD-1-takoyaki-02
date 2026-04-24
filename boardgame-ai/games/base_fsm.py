"""게임 FSM 추상 베이스 클래스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.envelope import WSMessage
from core.events import FusionContext, GameEvent


class BaseFSM(ABC):
    """모든 게임 FSM이 구현해야 하는 인터페이스."""

    @abstractmethod
    def handle_event(self, event: GameEvent) -> list[WSMessage]:
        """비전 파이프라인에서 GameEvent 수신 후 처리."""
        ...

    @abstractmethod
    def handle_input(
        self,
        input_type: str,
        data: dict,
        player_id: str | None = None,
    ) -> list[WSMessage]:
        """UI에서 입력 수신 후 처리."""
        ...

    @abstractmethod
    def get_fusion_context(self) -> FusionContext:
        """현재 phase에 맞는 FusionContext 반환. FSM 전이마다 broadcast."""
        ...

    @abstractmethod
    def get_state_dict(self) -> dict:
        """현재 게임 상태를 dict로 반환. state_update 페이로드에 사용."""
        ...
