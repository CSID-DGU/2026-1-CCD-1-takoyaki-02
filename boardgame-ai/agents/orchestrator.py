"""에이전트 오케스트레이터 — 우선순위 기반 에이전트 중재자.

우선순위 (낮을수록 높음):
  1. RulesAgent   (CRITICAL) — 규칙 위반 감지 시 즉시 개입, 하위 억제
  2. TempoAgent   (HIGH)     — 턴 타이머 마일스톤 알림 (백그라운드 태스크)
  3. ProgressAgent(NORMAL)   — 페이즈 전환 진행 내러티브
  4. StrategyAgent(LOW)      — 의사결정 시점 전략 추천 (활성화 시만)

사용:
    orchestrator = AgentOrchestrator(audio_manager)
    # 세션에서 FSM 상태 전환 시
    await orchestrator.on_state_change(ctx)
    # 세션에서 게임 이벤트 수신 시
    await orchestrator.on_game_event(event)
    # 전략 코칭 토글
    orchestrator.set_strategy_enabled(True)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from core.audio import AudioPriority
from core.constants import AgentRole
from core.events import GameEvent

from agents.base import Intervention
from agents.context import AgentContext
from agents.progress_agent import ProgressAgent
from agents.rules_agent import RulesAgent
from agents.strategy_agent import StrategyAgent
from agents.tempo_agent import TempoAgent

if TYPE_CHECKING:
    from audio.manager import AudioManager

logger = logging.getLogger(__name__)

_AGENT_ROLE_MAP: dict[str, str] = {
    "rules":    AgentRole.REFEREE.value,
    "tempo":    AgentRole.TEMPO.value,
    "progress": AgentRole.NARRATOR.value,
    "strategy": AgentRole.STRATEGY.value,
}


class AgentOrchestrator:
    def __init__(self, audio_manager: AudioManager) -> None:
        self._audio = audio_manager
        self._rules = RulesAgent()
        self._tempo = TempoAgent()
        self._progress = ProgressAgent()
        self._strategy = StrategyAgent()
        self._current_ctx: AgentContext | None = None
        self._state_version: int = 0

        self._tempo.set_tts_callback(
            lambda text, prio: self._send_tts(text, prio, AgentRole.TEMPO.value)
        )

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def set_strategy_enabled(self, enabled: bool) -> None:
        self._strategy.set_enabled(enabled)

    @property
    def strategy_enabled(self) -> bool:
        return self._strategy.enabled

    async def on_state_change(self, ctx: AgentContext, state_version: int = 0) -> None:
        """FSM 상태 전환 시 세션에서 호출."""
        self._current_ctx = ctx
        self._state_version = state_version

        # 1) 템포 타이머 재시작 (sync, 내부적으로 asyncio.create_task)
        self._tempo.on_state_change(ctx)

        # 2) 진행 에이전트 — 새 페이즈 안내
        result = self._progress.on_state_change(ctx)
        if result:
            await self._dispatch(result)
            if result.suppress_lower:
                return

        # 3) 전략 에이전트 — 백그라운드로 실행 (지연이 있어도 게임 흐름 차단 없음)
        asyncio.create_task(self._run_strategy(ctx))

    async def on_game_event(self, event: GameEvent) -> None:
        """게임 이벤트 수신 시 세션에서 호출 (FSM 처리 이전에 호출 권장)."""
        if self._current_ctx is None:
            return
        result = self._rules.on_game_event(event, self._current_ctx)
        if result:
            await self._dispatch(result)

    def stop(self) -> None:
        """세션 종료 시 호출 — 백그라운드 타이머 정리."""
        self._tempo.stop()

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    async def _run_strategy(self, ctx: AgentContext) -> None:
        result = self._strategy.on_state_change(ctx)
        if result:
            await self._dispatch(result)

    async def _dispatch(self, intervention: Intervention) -> None:
        if intervention.tts_text:
            await self._send_tts(
                intervention.tts_text,
                intervention.priority,
                agent=_AGENT_ROLE_MAP.get(intervention.agent, AgentRole.NARRATOR.value),
            )

    async def _send_tts(
        self,
        text: str,
        priority: AudioPriority,
        agent: str = AgentRole.NARRATOR.value,
    ) -> None:
        try:
            await self._audio.enqueue_tts(
                text=text,
                agent=agent,
                priority=priority,
                state_version=self._state_version,
            )
        except Exception:
            logger.exception("[AgentOrchestrator] TTS 전송 실패 (agent=%s)", agent)
