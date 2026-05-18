"""진행 에이전트 — FSM 상태 전환마다 NORMAL 우선순위 TTS로 진행을 안내.

FSM이 이미 내보내는 TTS와 중복을 피하기 위해, 이 에이전트는 FSM이 다루지 않는
상위 레벨 내러티브(페이즈 전환 배경음성)를 담당한다.
스크립트는 게임별 dict로 관리하며, {player} 등 템플릿 변수를 지원한다.
"""

from __future__ import annotations

from agents.base import BaseAgent, Intervention
from agents.context import AgentContext
from core.audio import AudioPriority


# ── 늑대인간 페이즈 스크립트 ────────────────────────────────────────────────────
# FSM이 이미 안내하는 상태는 여기서 제외. ProgressAgent는 FSM 미담당 보조 안내만.
# FSM 담당: night_start, 각 night_* 역할 호출, day_discussion, vote, result
# ProgressAgent 담당: FSM이 명시적으로 안내하지 않는 전환 보조 멘트
_WEREWOLF_SCRIPTS: dict[str, str] = {
    "vote_countdown": "곧 투표가 시작됩니다. 의심스러운 플레이어를 생각해두세요.",
}

# ── 요트다이스 페이즈 스크립트 ──────────────────────────────────────────────────
# FSM이 이미 "{player}님, 주사위를 굴려주세요" 등을 안내하므로 여기서는 제외.
# ProgressAgent는 FSM 미담당 보조 안내만.
_YACHT_SCRIPTS: dict[str, str] = {}

_SCRIPTS: dict[str, dict[str, str]] = {
    "werewolf": _WEREWOLF_SCRIPTS,
    "yacht":    _YACHT_SCRIPTS,
}


class ProgressAgent(BaseAgent):
    """우선순위 3 (NORMAL). 페이즈 전환마다 진행 내러티브를 안내한다."""

    name = "progress"

    def __init__(self) -> None:
        self._last_state: str = ""

    def on_state_change(self, ctx: AgentContext) -> Intervention | None:
        # 같은 상태로 중복 호출 방지
        if ctx.fsm_state == self._last_state:
            return None
        self._last_state = ctx.fsm_state

        scripts = _SCRIPTS.get(ctx.game_type, {})
        template = scripts.get(ctx.fsm_state)
        if not template:
            return None

        player_name = ctx.player_name(ctx.active_player) or ""
        text = template.replace("{player}", player_name)

        return Intervention(
            agent=self.name,
            tts_text=text,
            priority=AudioPriority.NORMAL,
            suppress_lower=False,  # 전략 에이전트와 공존 가능
        )
