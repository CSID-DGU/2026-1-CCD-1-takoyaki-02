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
_WEREWOLF_SCRIPTS: dict[str, str] = {
    "night_start":        "밤이 시작됩니다. 모두 눈을 감아주세요.",
    "night_doppelganger": "도플갱어, 눈을 뜨고 모방할 역할을 선택하세요.",
    "night_werewolf":     "늑대인간, 눈을 뜨고 서로를 확인하세요.",
    "night_minion":       "하수인, 눈을 떠서 늑대인간을 확인하세요.",
    "night_mason":        "프리메이슨, 눈을 뜨고 서로를 확인하세요.",
    "night_seer":         "예언자, 눈을 뜨고 확인할 카드를 선택하세요.",
    "night_robber":       "도둑, 눈을 뜨고 다른 플레이어의 카드와 교환할 수 있습니다.",
    "night_troublemaker": "말썽꾼, 눈을 뜨고 두 플레이어의 카드를 교환할 수 있습니다.",
    "night_drunk":        "술꾼, 눈을 뜨고 센터 카드를 가져가세요.",
    "night_insomniac":    "불면증 환자, 눈을 뜨고 자신의 최종 카드를 확인하세요.",
    "day_discussion":     "날이 밝았습니다. 토론을 시작하세요. 마을의 적을 찾아야 합니다.",
    "vote_countdown":     "곧 투표가 시작됩니다. 의심스러운 플레이어를 생각해두세요.",
    "vote":               "투표 시간입니다. 의심스러운 플레이어를 지목하세요.",
    "result":             "결과를 확인하겠습니다.",
}

# ── 요트다이스 페이즈 스크립트 ──────────────────────────────────────────────────
# {player}: 현재 플레이어 이름으로 치환됨
_YACHT_SCRIPTS: dict[str, str] = {
    "AWAITING_ROLL":  "{player}님, 주사위를 굴려주세요.",
    "AWAITING_KEEP":  "{player}님, 유지할 주사위를 선택하세요.",
    "AWAITING_SCORE": "{player}님, 점수를 기록할 카테고리를 선택하세요.",
    "GAME_END":       "게임이 종료됐습니다! 수고하셨습니다.",
}

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
