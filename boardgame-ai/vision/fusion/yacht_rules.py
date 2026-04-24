"""요트다이스 전용 Fusion 규칙.

event_type 문자열 상수만 여기서 정의.
실제 FSM enum은 FSM 팀(강병진) 영역이므로 import 하지 않음 (core 규칙).

지원 이벤트:
  ROLL_CONFIRMED : 굴림 완료 + actor 확정 (핵심 이벤트)
"""

from __future__ import annotations

from core.events import FusionContext
from vision.schemas import FramePerception

# ── 요트 전용 event_type 문자열 상수 ─────────────────────────────────────────
ROLL_CONFIRMED = "ROLL_CONFIRMED"
DICE_KEEP_SELECTED = "DICE_KEEP_SELECTED"
DICE_REROLL_REQUESTED = "DICE_REROLL_REQUESTED"
SCORE_CATEGORY_SELECTED = "SCORE_CATEGORY_SELECTED"

# FSM 팀과 합의된 요트 Phase 문자열
PHASE_AWAITING_ROLL = "AWAITING_ROLL"
PHASE_AWAITING_KEEP = "AWAITING_KEEP"
PHASE_AWAITING_SCORE = "AWAITING_SCORE"


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

        if ctx.fsm_state == PHASE_AWAITING_ROLL:
            c = self._check_roll_confirmed(perception, ctx)
            if c:
                candidates.append(c)

        return candidates

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _check_roll_confirmed(
        self, perception: FramePerception, ctx: FusionContext | None = None
    ) -> tuple[str, object, float] | None:
        """roll_actor_id + 주사위 안정 → ROLL_CONFIRMED 후보.
        pip_count가 None인 주사위도 허용 (부분 인식 시에도 이벤트 발생).
        roll_actor_id 없으면 ctx.active_player로 fallback (플레이어 미등록 환경).
        """
        actor_id = perception.roll_actor_id
        if actor_id is None and ctx is not None:
            actor_id = ctx.active_player
        if actor_id is None:
            return None
        if not perception.dice:
            return None

        values = [d.pip_count for d in perception.dice]
        known = [v for v in values if v is not None]
        if not known:
            return None

        conf = 0.95 if len(known) == len(values) else 0.75
        # stab_key는 actor + 주사위 개수만 — pip 값이 프레임마다 미세하게 달라도
        # 안정화 카운터가 리셋되지 않게 하기 위함
        data_key = (actor_id, len(perception.dice))
        data = {
            "actor_id": actor_id,
            "dice_values": values,
            "keep_mask": [False] * len(values),
        }
        return ROLL_CONFIRMED, {"_key": data_key, **data}, conf
