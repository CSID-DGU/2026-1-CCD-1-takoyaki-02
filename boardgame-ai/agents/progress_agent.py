"""진행 에이전트 — FSM 상태 전환마다 NORMAL 우선순위 TTS로 진행을 안내.

모든 TTS 발화는 FSM이 아닌 이 에이전트가 전담한다.
- 요트: FSM의 last_message를 읽어 매 굴림/상태마다 동적으로 발화.
- 늑대인간: 페이즈별 고정 스크립트(_WEREWOLF_SCRIPTS)를 사용하며, 중복 발화를 방지.
스크립트는 게임별 dict로 관리하며, {player} 등 템플릿 변수를 지원한다.
"""

from __future__ import annotations

from agents.base import BaseAgent, Intervention
from agents.context import AgentContext
from core.audio import AudioPriority


# ── 늑대인간 페이즈 스크립트 ────────────────────────────────────────────────────
# FSM은 상태 전환만 담당. TTS 발화는 ProgressAgent가 전담.
# catalog.py STATIC_LINES와 동일 문자열 → AudioManager static 캐시 hit.
# vote_countdown/final_role_reveal/result는 FUSION_CONTEXT를 emit하지 않으므로 제외.
_WEREWOLF_SCRIPTS: dict[str, str] = {
    "night_start":        "밤이 되었습니다. 모두 눈을 감아주세요.",
    "night_doppelganger": "도플갱어는 깨어나세요. 다른 플레이어 1명의 카드를 확인하세요. 그 역할이 됩니다.",
    "night_werewolf":     "늑대인간은 깨어나세요. 서로를 확인하고 다시 눈을 감으세요.",
    "night_minion":       "하수인은 깨어나세요. 늑대인간들은 엄지를 들어올려 자신을 알려주세요.",
    "night_mason":        "프리메이슨은 깨어나세요. 서로를 확인하고 다시 눈을 감으세요.",
    "night_seer":         "예언자는 깨어나세요. 다른 플레이어 1명 또는 중앙 카드 2장을 확인할 수 있습니다.",
    "night_robber":       "도둑은 깨어나세요. 다른 플레이어 1명의 카드와 자신의 카드를 교환할 수 있습니다.",
    "night_troublemaker": "말썽꾼은 깨어나세요. 자신을 제외한 두 플레이어의 카드를 서로 교환하세요.",
    "night_drunk":        "술꾼은 깨어나세요. 중앙 카드 1장을 가져와 자신의 카드와 교환하세요. 새 카드는 볼 수 없습니다.",
    "night_insomniac":    "불면증환자는 깨어나세요. 자신의 카드를 확인하세요.",
    # day_discussion: NightEnd 컴포넌트가 "아침이 밝았습니다 → 토론 시작" 순서를 관리.
    # ProgressAgent가 여기서 발화하면 NightEnd TTS와 순서 충돌 → 제거.
    "vote":               "투표를 시작합니다. 제거할 플레이어를 손으로 가리키세요.",
}

_SCRIPTS: dict[str, dict[str, str]] = {
    "werewolf": _WEREWOLF_SCRIPTS,
}


class ProgressAgent(BaseAgent):
    """우선순위 3 (NORMAL). 페이즈 전환마다 진행 내러티브를 안내한다."""

    name = "progress"

    def __init__(self) -> None:
        self._last_state: str = ""

    def on_state_change(self, ctx: AgentContext) -> Intervention | None:
        if ctx.game_type == "yacht":
            return self._yacht_progress(ctx)
        return self._werewolf_progress(ctx)

    def _yacht_progress(self, ctx: AgentContext) -> Intervention | None:
        # 요트는 같은 fsm_state(awaiting_keep 등)가 매 굴림마다 반복되므로
        # 상태명 중복 체크 대신 last_message 내용으로 TTS 발화를 결정한다.
        text = ctx.game_specific.get("last_message", "")
        if not text:
            return None
        return Intervention(
            agent=self.name,
            tts_text=text,
            priority=AudioPriority.NORMAL,
            suppress_lower=False,
        )

    def _werewolf_progress(self, ctx: AgentContext) -> Intervention | None:
        # 같은 상태로 중복 호출 방지 (늑대인간 페이즈는 게임 내 반복되지 않음)
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
