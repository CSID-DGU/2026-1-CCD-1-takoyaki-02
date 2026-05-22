"""전략 에이전트 — 활성화 시 의사결정 시점에 전략 추천을 제공.

요트다이스: 현재 주사위 조합 기준 가장 유리한 카테고리를 계산해 안내.
늑대인간: 야간 페이즈별 역할에 맞는 행동 지침을 안내.

set_enabled(True) 호출 시 활성화. 기본은 비활성.
game_specific에서 필요한 정보를 읽는다.
  - 요트: {"dice_values": [1,2,3,4,5], "available_categories": [...], "roll_count": N}
  - 늑대인간: {"active_role": "seer"} (옵션 — 없으면 페이즈 기준 안내)
"""

from __future__ import annotations

from agents.base import BaseAgent, Intervention
from agents.context import AgentContext
from core.audio import AudioPriority

# ── 요트다이스: 카테고리 한글명 ──────────────────────────────────────────────────
_CATEGORY_KO: dict[str, str] = {
    "ones":          "1",
    "twos":          "2",
    "threes":        "3",
    "fours":         "4",
    "fives":         "5",
    "sixes":         "6",
    "choice":        "찬스",
    "four_of_a_kind": "포카인드",
    "full_house":    "풀하우스",
    "small_straight": "스몰스트레이트",
    "large_straight": "라지스트레이트",
    "yacht":         "요트",
}

# ── 늑대인간: 야간 페이즈별 역할 행동 지침 ─────────────────────────────────────
_WEREWOLF_PHASE_TIPS: dict[str, str] = {
    # 패시브 야간 페이즈(night_werewolf, night_minion, night_mason)는
    # 해당 역할이 행동 없이 서로를 확인만 하므로 전략 팁 불필요 → 의도적으로 제외.
    "night_doppelganger": (
        "도플갱어는 다른 플레이어의 카드를 몰래 확인해 그 역할을 복사합니다. "
        "강력한 역할(예언자, 도둑)을 노리세요."
    ),
    "night_seer": (
        "예언자는 다른 플레이어 카드 한 장 또는 센터 카드 두 장을 볼 수 있습니다. "
        "의심스러운 플레이어의 카드를 확인하는 것이 효과적입니다."
    ),
    "night_robber": (
        "도둑은 다른 플레이어와 카드를 교환할 수 있습니다. "
        "강력한 역할을 가진 플레이어의 카드를 노리세요."
    ),
    "night_troublemaker": (
        "말썽꾼은 두 플레이어의 카드를 교환합니다. "
        "늑대인간으로 의심되는 플레이어와 다른 플레이어의 카드를 바꿔 혼란을 주세요."
    ),
    "night_drunk": (
        "술꾼은 센터 카드 중 하나와 자신의 카드를 교환합니다. "
        "자신의 새 역할을 알 수 없으니 낮 토론에서 신중하게 행동하세요."
    ),
    "night_insomniac": (
        "불면증 환자는 밤이 끝난 후 자신의 최종 카드를 확인합니다. "
        "카드가 바뀌었다면 누군가 손을 댔다는 단서가 됩니다."
    ),
}

# 요트 의사결정 시점 페이즈
_YACHT_STRATEGY_PHASES = frozenset({"AWAITING_KEEP", "AWAITING_SCORE"})
# 늑대 전략 제공 페이즈
_WEREWOLF_STRATEGY_PHASES = frozenset(_WEREWOLF_PHASE_TIPS.keys())


class StrategyAgent(BaseAgent):
    """우선순위 4 (LOW). 활성화 시 의사결정 시점에 전략 추천을 안내한다."""

    name = "strategy"

    def __init__(self) -> None:
        self._enabled: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def on_state_change(self, ctx: AgentContext) -> Intervention | None:
        if not self._enabled:
            return None

        if ctx.game_type == "yacht":
            return self._yacht_strategy(ctx)
        if ctx.game_type == "werewolf":
            return self._werewolf_strategy(ctx)
        return None

    # ── 요트다이스 전략 ────────────────────────────────────────────────────────

    def _yacht_strategy(self, ctx: AgentContext) -> Intervention | None:
        if ctx.fsm_state not in _YACHT_STRATEGY_PHASES:
            return None
        gs = ctx.game_specific
        dice: list[int | None] = gs.get("dice_values", [])
        available: list[str] = gs.get("available_categories", [])
        if not dice or not available:
            return None

        text = self._best_category_tip(dice, available)
        if not text:
            return None
        return Intervention(
            agent=self.name,
            tts_text=text,
            priority=AudioPriority.LOW,
            suppress_lower=False,
        )

    def _best_category_tip(
        self, dice: list[int | None], available: list[str]
    ) -> str | None:
        try:
            from games.yacht.scoring import calculate_score
        except ImportError:
            return None

        if any(v is None for v in dice):
            return None

        scores: list[tuple[int, str]] = []
        for cat in available:
            try:
                s = calculate_score(cat, dice)
                scores.append((s, cat))
            except Exception:
                continue

        if not scores:
            return None

        scores.sort(key=lambda x: x[0], reverse=True)
        best_score, best_cat = scores[0]
        cat_ko = _CATEGORY_KO.get(best_cat, best_cat)

        if best_score == 0:
            # 점수가 나오는 카테고리가 없으면 최소 피해를 권장
            return f"현재 주사위로 점수가 나오는 카테고리가 없습니다. 낮은 값을 가진 카테고리에 0을 기록하는 것을 추천합니다."

        return f"현재 주사위 조합에서는 {cat_ko}에 기록하면 {best_score}점을 얻을 수 있습니다."

    # ── 늑대인간 전략 ──────────────────────────────────────────────────────────

    def _werewolf_strategy(self, ctx: AgentContext) -> Intervention | None:
        if ctx.fsm_state not in _WEREWOLF_STRATEGY_PHASES:
            return None
        tip = _WEREWOLF_PHASE_TIPS.get(ctx.fsm_state)
        if not tip:
            return None
        return Intervention(
            agent=self.name,
            tts_text=tip,
            priority=AudioPriority.LOW,
            suppress_lower=False,
        )
