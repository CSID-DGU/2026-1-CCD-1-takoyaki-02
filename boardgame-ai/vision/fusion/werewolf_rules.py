"""한밤의 늑대인간 전용 Fusion 규칙.

games/werewolf/ontology.py 직접 import 금지 — vision↔games 분리 규칙.
FSM 팀과 합의된 문자열 상수를 이 파일에서만 관리.

지원 이벤트:
  CARD_PEEK  : 야간 페이즈에서 카드 앞면 전환 감지 (예언자/불면증)
  CARD_SWAP  : 야간 페이즈에서 카드 교환 제스처 감지 (도둑/말썽꾼/술꾼)
  VOTE_POINT : 투표 페이즈에서 뒤집힌 카드를 손목 벡터로 가리킴 감지

감지 전략:
  CARD_PEEK  → TrackedCard.just_flipped_up == True (face_down→face_up 전환 프레임)
  CARD_SWAP  → grab 제스처(카드 A 근처) → release 제스처(카드 B 근처) 순서
  VOTE_POINT → 손목[0]→검지끝[8] 방향 벡터 연장선이 face_down 카드 bbox 와 교차
"""

from __future__ import annotations

import math

from core.events import FusionContext
from vision.schemas import FramePerception, HandDet
from vision.werewolf.card_tracker import CardTracker
from vision.werewolf.schemas import TrackedCard

# ── FSM 팀과 합의된 문자열 상수 ────────────────────────────────────────────────
# games/werewolf/ontology.py 의 WerewolfEventType / WerewolfPhase 와 동일한 값
CARD_PEEK = "werewolf_card_peek"
CARD_SWAP = "werewolf_card_swap"
VOTE_POINT = "werewolf_vote_point"

_PHASE_NIGHT_SEER = "night_seer"
_PHASE_NIGHT_INSOMNIAC = "night_insomniac"
_PHASE_NIGHT_ROBBER = "night_robber"
_PHASE_NIGHT_TROUBLEMAKER = "night_troublemaker"
_PHASE_NIGHT_DRUNK = "night_drunk"
_PHASE_VOTE = "vote"

# ── 감지 파라미터 ───────────────────────────────────────────────────────────────
_GRAB_DIST_THRESHOLD = 0.08   # 손목-카드 중심 최대 거리 (grab/release 판정)
_MIN_POINT_LENGTH = 0.03      # 손목→검지끝 최소 거리 (포인팅 제스처 판별)
_RAY_MAX_T = 1.5              # ray cast 최대 거리 (정규화)


class WerewolfRules:
    """늑대인간 비전 이벤트 후보 생성기.

    FusionEngine 이 instantiate 하지 않고,
    WerewolfVisionPipeline 에서 CardTracker 참조와 함께 생성해
    FusionEngine.register_werewolf_rules() 로 주입한다.
    """

    def __init__(self, card_tracker: CardTracker) -> None:
        self._card_tracker = card_tracker
        self._last_phase: str = ""
        # CARD_PEEK 중복 발화 방지: (actor_id, card_owner_id, card_index)
        self._reported_peeks: set[tuple] = set()
        # CARD_SWAP 중복 발화 방지: (actor_id, id_a, id_b) — 두 id 정렬
        self._reported_swaps: set[tuple] = set()
        # CARD_SWAP 첫 번째 grab 기억: actor_id → (track_id, id_str)
        self._swap_first_touch: dict[str, tuple[int, str]] = {}
        # VOTE_POINT: voter_id → 이미 투표한 target_id (1인 1표)
        self._votes_cast: dict[str, str] = {}

    def build_candidates(
        self,
        ctx: FusionContext,
        perception: FramePerception,
    ) -> list[tuple[str, dict, float]]:
        """FusionEngine.feed() 에서 호출.

        Returns
        -------
        list of (event_type, data_dict_with_key, confidence)
        """
        phase = ctx.fsm_state

        # 페이즈 전환 시 내부 상태 리셋 (중복 발화 방지 집합 초기화)
        if phase != self._last_phase:
            self._last_phase = phase
            self._reported_peeks.clear()
            self._reported_swaps.clear()
            self._swap_first_touch.clear()
            self._votes_cast.clear()

        tracked = self._card_tracker.get_tracked_cards()
        candidates: list[tuple[str, dict, float]] = []

        if phase in (_PHASE_NIGHT_SEER, _PHASE_NIGHT_INSOMNIAC):
            c = self._check_card_peek(perception, ctx, tracked)
            if c:
                candidates.append(c)

        elif phase in (_PHASE_NIGHT_ROBBER, _PHASE_NIGHT_TROUBLEMAKER, _PHASE_NIGHT_DRUNK):
            c = self._check_card_swap(perception, ctx, tracked)
            if c:
                candidates.append(c)

        elif phase == _PHASE_VOTE:
            for hand in perception.hands:
                c = self._check_vote_point(hand, ctx, tracked)
                if c:
                    candidates.append(c)

        return candidates

    # ── CARD_PEEK ────────────────────────────────────────────────────────────────

    def _check_card_peek(
        self,
        perception: FramePerception,
        ctx: FusionContext,
        tracked: list[TrackedCard],
    ) -> tuple[str, dict, float] | None:
        """카드가 face_down → face_up 으로 전환된 프레임을 CARD_PEEK 후보로 반환.

        valid_targets 에 포함된 카드만 유효 대상으로 인정.
        """
        actor_id = ctx.active_player
        if not actor_id:
            return None

        valid_targets = ctx.valid_targets or {}
        allowed_player_ids: list[str] = valid_targets.get("player_ids", [])
        allowed_center_ids: list[str] = valid_targets.get("center_ids", [])
        self_only: bool = bool(valid_targets.get("self_only", False))

        for card in tracked:
            if not card.just_flipped_up:
                continue
            if card.cls_name is None:
                # 한 번도 앞면으로 감지된 적 없는 카드 — 역할 불명, skip
                continue

            if card.player_id is not None:
                # 플레이어 카드
                if self_only and card.player_id != actor_id:
                    continue
                if not self_only and card.player_id not in allowed_player_ids:
                    continue
                peek_key = (actor_id, card.player_id, card.card_index)
                if peek_key in self._reported_peeks:
                    continue
                self._reported_peeks.add(peek_key)
                data = {
                    "actor_id": actor_id,
                    "card_owner_id": card.player_id,
                    "card_index": card.card_index,
                    "_key": peek_key,
                }
                return CARD_PEEK, data, 0.9
            else:
                # 센터 카드
                center_id = f"center_{card.card_index}"
                if center_id not in allowed_center_ids:
                    continue
                peek_key = (actor_id, None, card.card_index)
                if peek_key in self._reported_peeks:
                    continue
                self._reported_peeks.add(peek_key)
                data = {
                    "actor_id": actor_id,
                    "card_owner_id": None,
                    "card_index": card.card_index,
                    "_key": peek_key,
                }
                return CARD_PEEK, data, 0.9

        return None

    # ── CARD_SWAP ────────────────────────────────────────────────────────────────

    def _check_card_swap(
        self,
        perception: FramePerception,
        ctx: FusionContext,
        tracked: list[TrackedCard],
    ) -> tuple[str, dict, float] | None:
        """grab 제스처(카드 A) → release 제스처(카드 B) 순서로 CARD_SWAP 감지.

        actor_id(ctx.active_player) 의 손만 추적한다.
        NIGHT_DRUNK 는 from_id=actor_id, to_id=center_N 형태여야 FSM 이 수용.
        """
        actor_id = ctx.active_player
        if not actor_id:
            return None

        for hand in perception.hands:
            if hand.player_id != actor_id:
                continue

            if hand.gesture == "grab":
                card = _find_nearest_card(hand.wrist_xy, tracked, _GRAB_DIST_THRESHOLD)
                if card is not None:
                    card_id = card.player_id or f"center_{card.card_index}"
                    self._swap_first_touch[actor_id] = (card.track_id, card_id)

            elif hand.gesture == "release":
                if actor_id not in self._swap_first_touch:
                    continue
                first_track_id, from_id = self._swap_first_touch[actor_id]
                card = _find_nearest_card(hand.wrist_xy, tracked, _GRAB_DIST_THRESHOLD)
                if card is None or card.track_id == first_track_id:
                    continue
                to_id = card.player_id or f"center_{card.card_index}"
                swap_key = (actor_id, min(from_id, to_id), max(from_id, to_id))
                if swap_key in self._reported_swaps:
                    continue
                self._reported_swaps.add(swap_key)
                del self._swap_first_touch[actor_id]
                data = {
                    "actor_id": actor_id,
                    "from_id": from_id,
                    "to_id": to_id,
                    "_key": swap_key,
                }
                return CARD_SWAP, data, 0.85

        return None

    # ── VOTE_POINT ───────────────────────────────────────────────────────────────

    def _check_vote_point(
        self,
        hand: HandDet,
        ctx: FusionContext,
        tracked: list[TrackedCard],
    ) -> tuple[str, dict, float] | None:
        """손목[0]→검지끝[8] 방향 벡터 연장선이 face_down 카드 bbox 와 교차하면 VOTE_POINT.

        1인 1표 — 이미 투표한 voter_id 는 skip.
        """
        voter_id = hand.player_id
        if not voter_id:
            return None
        if voter_id in self._votes_cast:
            return None
        if not hand.landmarks_21 or len(hand.landmarks_21) < 9:
            return None

        wrist = hand.landmarks_21[0]      # landmark 0
        index_tip = hand.landmarks_21[8]  # landmark 8

        dx = index_tip[0] - wrist[0]
        dy = index_tip[1] - wrist[1]
        length = math.hypot(dx, dy)

        if length < _MIN_POINT_LENGTH:
            return None  # 검지가 접혀 있음

        nx, ny = dx / length, dy / length

        for card in tracked:
            if card.face_up:
                continue  # 뒤집힌 카드만 투표 대상
            if card.player_id is None:
                continue  # 센터 카드는 투표 대상 아님
            if not _ray_hits_bbox(wrist, (nx, ny), card.bbox, _RAY_MAX_T):
                continue

            self._votes_cast[voter_id] = card.player_id
            data = {
                "actor_id": voter_id,
                "target_id": card.player_id,
                "_key": (voter_id, card.player_id),
            }
            return VOTE_POINT, data, 0.85

        return None


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

def _find_nearest_card(
    wrist_xy: tuple[float, float],
    tracked: list[TrackedCard],
    threshold: float,
) -> TrackedCard | None:
    """wrist_xy 에서 가장 가까운 카드 반환. threshold 초과면 None."""
    wx, wy = wrist_xy
    best: TrackedCard | None = None
    best_dist = threshold
    for card in tracked:
        dist = math.hypot(card.bbox.cx - wx, card.bbox.cy - wy)
        if dist < best_dist:
            best_dist = dist
            best = card
    return best


def _ray_hits_bbox(
    origin: tuple[float, float],
    direction: tuple[float, float],
    bbox: object,
    max_t: float,
) -> bool:
    """AABB 레이-박스 교차 검사 (정규화 좌표 기준).

    origin 에서 direction 방향으로 뻗은 반직선이 bbox 와 교차하면 True.
    t ∈ [0, max_t] 범위만 검사.
    """
    ox, oy = origin
    dx, dy = direction

    if abs(dx) < 1e-9:
        # 수직 방향 — x 가 bbox 범위 안에 있는지만 확인
        txmin = float("-inf") if bbox.x1 <= ox <= bbox.x2 else float("inf")
        txmax = float("inf") if bbox.x1 <= ox <= bbox.x2 else float("-inf")
    else:
        txmin = (bbox.x1 - ox) / dx
        txmax = (bbox.x2 - ox) / dx
        if txmin > txmax:
            txmin, txmax = txmax, txmin

    if abs(dy) < 1e-9:
        tymin = float("-inf") if bbox.y1 <= oy <= bbox.y2 else float("inf")
        tymax = float("inf") if bbox.y1 <= oy <= bbox.y2 else float("-inf")
    else:
        tymin = (bbox.y1 - oy) / dy
        tymax = (bbox.y2 - oy) / dy
        if tymin > tymax:
            tymin, tymax = tymax, tymin

    t_enter = max(txmin, tymin, 0.0)
    t_exit = min(txmax, tymax, max_t)

    return t_enter <= t_exit
