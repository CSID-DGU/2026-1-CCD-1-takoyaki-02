"""요트다이스 전용 Fusion 규칙.

event_type 문자열 상수만 여기서 정의.
실제 FSM enum은 FSM 팀(강병진) 영역이므로 import 하지 않음 (core 규칙).

지원 이벤트:
  dice_stable    : 주사위 5개 모두 안정 (중간 확인용, FSM이 무시 가능)
  dice_rolled    : 굴림 완료 + actor 확정 (핵심 이벤트)
"""

from __future__ import annotations

from core.events import FusionContext
from vision.schemas import FramePerception

# ── 요트 전용 event_type 문자열 상수 ─────────────────────────────────────────
DICE_STABLE = "dice_stable"
DICE_ROLLED = "dice_rolled"
DICE_KEEP_SELECTED = "dice_keep_selected"
DICE_REROLL_REQUESTED = "dice_reroll_requested"
SCORE_CATEGORY_SELECTED = "score_category_selected"

# FSM 팀과 합의할 요트 Phase 문자열
PHASE_WAITING_ROLL = "waiting_roll"
PHASE_WAITING_KEEP = "waiting_keep"
PHASE_WAITING_SCORE = "waiting_score"


class YachtRules:
    """요트다이스 비전 이벤트 후보 생성기."""

    def build_candidates(
        self,
        ctx: FusionContext,
        perception: FramePerception,
    ) -> list[tuple[str, object, float]]:
        """
        Returns
        -------
        list of (event_type, data_key, confidence)
        FusionEngine.feed()가 3조건 필터를 적용한다.
        """
        candidates: list[tuple[str, object, float]] = []

        if ctx.fsm_state == PHASE_WAITING_ROLL:
            c = self._check_dice_rolled(perception)
            if c:
                candidates.append(c)

        # dice_stable은 모든 요트 phase에서 후보로 올림 (FSM이 expected에 넣을지 결정)
        s = self._check_dice_stable(perception, ctx)
        if s:
            candidates.append(s)

        return candidates

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _check_dice_rolled(
        self, perception: FramePerception
    ) -> tuple[str, object, float] | None:
        """roll_actor_id + 주사위 안정 → dice_rolled 후보.
        pip_count가 None인 주사위도 허용 (부분 인식 시에도 이벤트 발생).
        """
        if perception.roll_actor_id is None:
            return None
        if not perception.dice:
            return None

        values = [d.pip_count for d in perception.dice]
        known = [v for v in values if v is not None]
        # 아무것도 인식 못 했으면 보류
        if not known:
            return None

        conf = 0.95 if len(known) == len(values) else 0.75
        # stab_key는 actor + 주사위 개수만 — pip 값이 프레임마다 미세하게 달라도
        # 안정화 카운터가 리셋되지 않게 하기 위함
        data_key = (
            perception.roll_actor_id,
            len(perception.dice),
        )
        data = {
            "actor_id": perception.roll_actor_id,
            "dice_values": values,
            "keep_mask": [False] * len(values),
        }
        return DICE_ROLLED, {"_key": data_key, **data}, conf

    def _check_dice_stable(
        self, perception: FramePerception, ctx: FusionContext
    ) -> tuple[str, object, float] | None:
        """주사위가 모두 안정이면 dice_stable 후보."""
        from core.constants import DEFAULT_PARAMS
        stab = int(ctx.params.get("stabilization_frames", DEFAULT_PARAMS["stabilization_frames"]))
        if not perception.dice_all_stable(stab):
            return None

        values = [d.pip_count for d in perception.dice]
        data_key = ("dice_stable", tuple(v or 0 for v in values))
        data = {
            "dice_values": values,
            "dice_count": len(perception.dice),
            "actor_id": perception.roll_actor_id,
        }
        return DICE_STABLE, {"_key": data_key, **data}, 0.85
