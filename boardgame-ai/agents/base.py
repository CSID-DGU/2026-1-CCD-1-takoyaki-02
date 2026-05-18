"""에이전트 베이스 클래스 및 Intervention 타입."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from core.audio import AudioPriority
from core.events import GameEvent

from agents.context import AgentContext


@dataclass
class Intervention:
    """에이전트가 반환하는 개입 결과."""

    agent: str
    tts_text: str | None
    priority: AudioPriority
    suppress_lower: bool = True     # True면 하위 우선순위 에이전트를 이번 이벤트에서 건너뜀
    ui_payload: dict | None = None  # 프론트엔드로 별도 전송할 페이로드 (옵션)


class BaseAgent(ABC):
    name: str = "base"

    def on_state_change(self, ctx: AgentContext) -> Intervention | None:
        return None

    def on_game_event(self, event: GameEvent, ctx: AgentContext) -> Intervention | None:
        return None
