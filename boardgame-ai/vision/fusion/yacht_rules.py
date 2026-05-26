"""요트다이스 전용 Fusion 규칙.

event_type 문자열 상수만 여기서 정의.
실제 FSM enum은 FSM 팀 영역이므로 import 하지 않음 (core 규칙).

지원 이벤트:
  ROLL_CONFIRMED  : 굴림 완료 + 모든 주사위 pip 확정 (정상 경로)
  ROLL_UNREADABLE : 굴림 완료지만 일부 주사위 pip 인식 실패 (FSM에서 수동 입력 유도)
  DICE_ESCAPED    : 주사위가 tray bbox 밖으로 이탈 (재굴림 유도)
"""

from __future__ import annotations

from core.events import FusionContext
from vision.schemas import BBox
from vision.yacht.schemas import YachtFramePerception

# ── 요트 전용 event_type 문자열 상수 ─────────────────────────────────────────
ROLL_CONFIRMED = "ROLL_CONFIRMED"
ROLL_UNREADABLE = "ROLL_UNREADABLE"
DICE_ESCAPED = "DICE_ESCAPED"
DICE_KEEP_SELECTED = "DICE_KEEP_SELECTED"
DICE_REROLL_REQUESTED = "DICE_REROLL_REQUESTED"
SCORE_CATEGORY_SELECTED = "SCORE_CATEGORY_SELECTED"

# FSM 팀과 합의된 요트 Phase 문자열
PHASE_AWAITING_ROLL = "AWAITING_ROLL"
PHASE_AWAITING_KEEP = "AWAITING_KEEP"
PHASE_AWAITING_SCORE = "AWAITING_SCORE"


class YachtRules:
    """요트다이스 비전 이벤트 후보 생성기."""

    def __init__(self, escape_padding: float = 0.15) -> None:
        # tray 안에 있던 적이 있는 dice track_id 집합.
        # DICE_ESCAPED는 "안 → 밖" 전이일 때만 발화 — 처음부터 밖이면 가짜 detection 가능성.
        self._seen_inside: set[int] = set()
        # 이미 escaped 발화한 track_id — 다시 안으로 들어왔다 나가야 재발화 (반복 발화 차단).
        self._reported_escaped: set[int] = set()
        # tray bbox 외측 패딩 (tray 짧은 변 대비 비율).
        # 킵존 가장자리에 둔 dice가 tray 경계에 살짝 걸쳐 escape로 오인되는 것을 막는다.
        # tray 외부로 이 비율 이상 벗어나야 실제 이탈로 본다.
        self._escape_padding = escape_padding

    def build_candidates(
        self,
        ctx: FusionContext,
        perception: YachtFramePerception,
    ) -> list[tuple[str, object, float]]:
        """
        Returns
        -------
        list of (event_type, data_key, confidence)
        FusionEngine.feed()가 3조건 필터를 적용한다.
        """
        candidates: list[tuple[str, object, float]] = []

        if ctx.fsm_state in (PHASE_AWAITING_ROLL, PHASE_AWAITING_KEEP):
            c = self._check_roll_event(perception, ctx)
            if c:
                candidates.append(c)
            esc = self._check_dice_escaped(perception, ctx)
            if esc:
                candidates.append(esc)

        return candidates

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _check_roll_event(
        self, perception: YachtFramePerception, ctx: FusionContext | None = None
    ) -> tuple[str, object, float] | None:
        """주사위 안정 + actor 확정 시 ROLL_CONFIRMED 또는 ROLL_UNREADABLE 후보.

        - 모든 주사위 pip 인식 성공 → ROLL_CONFIRMED (conf 0.95)
        - 일부 인식 실패 → ROLL_UNREADABLE (conf 0.6) — FSM이 수동 입력 UI 띄우게 함
        - 전부 None → 후보 없음

        게이트: RollAttributor가 이번 프레임에 굴림을 finalize 했을 때만 후보 생성.
        정적 화면에서 N프레임 안정화 통과 → 무한 발화 루프를 막기 위함.
        """
        if not perception.roll_just_confirmed:
            return None

        actor_id = perception.roll_actor_id
        if actor_id is None and ctx is not None:
            actor_id = ctx.active_player
        if actor_id is None or not perception.dice:
            return None

        values = [d.pip_count for d in perception.dice]
        known = [v for v in values if v is not None]
        if not known:
            return None

        n = len(values)
        all_known = len(known) == n
        # stab_key는 actor + 주사위 개수만 — pip 미세 변동에도 안정화 카운터 유지
        data_key = (actor_id, n, "ok" if all_known else "partial")

        if all_known:
            data = {
                "actor_id": actor_id,
                "dice_values": values,
                "keep_mask": [False] * n,
            }
            return ROLL_CONFIRMED, {"_key": data_key, **data}, 0.95

        unknown_idx = [i for i, v in enumerate(values) if v is None]
        data = {
            "actor_id": actor_id,
            "dice_values": values,
            "unknown_indices": unknown_idx,
            "keep_mask": [False] * n,
        }
        return ROLL_UNREADABLE, {"_key": data_key, **data}, 0.6

    def _check_dice_escaped(
        self, perception: YachtFramePerception, ctx: FusionContext | None = None
    ) -> tuple[str, object, float] | None:
        """tray 안에 있던 dice가 밖으로 나간 경우만 DICE_ESCAPED 후보.

        - tray 미감지 시 무시 (오탐 방지).
        - 한 번이라도 tray 안에서 잡혔던 track_id 집합을 누적해 두고,
          그 중 어떤 게 이번 프레임에 tray 밖이면 발화 후보.
        - 처음부터 밖에서 잡힌 가짜 dice는 _seen_inside 에 안 들어가므로 무시.
        """
        tray = perception.tray
        if tray is None or not perception.dice:
            return None

        actor_id = perception.roll_actor_id
        if actor_id is None and ctx is not None:
            actor_id = ctx.active_player

        # 안/밖 판정에 hysteresis 적용 — 같은 좌표가 안/밖을 왔다갔다해도
        # 경계 dice(킵존 가장자리 등)가 escape로 오인되지 않는다.
        #  - 안 판정: tray bbox 그대로
        #  - 밖 판정: tray bbox + escape_padding (이만큼 벗어나야 진짜 escape)
        # 그 사이 회색 영역에 있는 dice는 직전 _seen_inside 상태를 유지.
        pad_x = (tray.x2 - tray.x1) * self._escape_padding
        pad_y = (tray.y2 - tray.y1) * self._escape_padding
        outer_x1, outer_y1 = tray.x1 - pad_x, tray.y1 - pad_y
        outer_x2, outer_y2 = tray.x2 + pad_x, tray.y2 + pad_y

        escaped_track_ids: list[int] = []
        for d in perception.dice:
            cx, cy = d.center
            inside_tight = _bbox_contains(tray, d.center)
            outside_loose = not (outer_x1 <= cx <= outer_x2 and outer_y1 <= cy <= outer_y2)
            if inside_tight:
                self._seen_inside.add(d.track_id)
                self._reported_escaped.discard(d.track_id)
            elif (
                outside_loose
                and d.track_id in self._seen_inside
                and d.track_id not in self._reported_escaped
            ):
                escaped_track_ids.append(d.track_id)

        if not escaped_track_ids:
            return None

        # 발화 직전 reported 집합에 등록 — 다음 프레임부터는 재발화 안 함
        for tid in escaped_track_ids:
            self._reported_escaped.add(tid)

        data_key = ("escaped", tuple(sorted(escaped_track_ids)))
        data = {
            "actor_id": actor_id,
            "escaped_track_ids": escaped_track_ids,
            "dice_count": len(perception.dice),
        }
        return DICE_ESCAPED, {"_key": data_key, **data}, 0.9


def _bbox_contains(bbox: BBox, point: tuple[float, float]) -> bool:
    x, y = point
    return bbox.x1 <= x <= bbox.x2 and bbox.y1 <= y <= bbox.y2
