"""한밤의 늑대인간 전용 Fusion 규칙.

games/werewolf/ontology.py 직접 import 금지 — vision↔games 분리 규칙.
FSM 팀과 합의된 문자열 상수를 이 파일에서만 관리.

지원 이벤트:
  ROLE_DETECTED: 역할 등록 단계에서 face_up 카드 안정적 감지
  CARD_PEEK    : 야간 페이즈에서 카드 앞면 전환 감지 (예언자/불면증)
  CARD_SWAP    : 야간 페이즈에서 카드 교환 제스처 감지 (도둑/말썽꾼/술꾼)
  VOTE_POINT   : 투표 페이즈에서 뒤집힌 카드를 손목 벡터로 가리킴 감지

감지 전략:
  ROLE_DETECTED → face_up 카드가 stable_frames >= 5 프레임 유지 시 발화 (1인당 1회)
  CARD_PEEK     → TrackedCard.just_flipped_up == True (face_down→face_up 전환 프레임)
  CARD_SWAP     → grab 제스처(카드 A 근처) → release 제스처(카드 B 근처) 순서
  VOTE_POINT    → 손목[0]→검지끝[8] 방향 벡터 연장선이 face_down 카드 bbox 와 교차
"""

from __future__ import annotations

import math

from core.events import FusionContext
from vision.schemas import FramePerception, HandDet
from vision.tracking.card_tracker import CardTracker
from vision.werewolf.schemas import TrackedCard

# ── FSM 팀과 합의된 문자열 상수 ────────────────────────────────────────────────
# games/werewolf/ontology.py 의 WerewolfEventType / WerewolfPhase 와 동일한 값
ROLE_DETECTED = "werewolf_role_detected"
CARD_PEEK = "werewolf_card_peek"
CARD_SWAP = "werewolf_card_swap"
VOTE_POINT = "werewolf_vote_point"
CARD_PLACED_DOWN = "werewolf_card_placed_down"
CARD_UNSTABLE    = "werewolf_card_unstable"

_PHASE_ROLE_REGISTRATION = "role_registration"
_PHASE_ROLE_REG_TRANSITION = "role_reg_transition"
# 투표 종료 후 카드가 바뀐 플레이어가 한 명씩 자기 카드를 다시 확인하는 단계.
# 등록 단계와 동일하게 ROLE_DETECTED 를 카메라로 감지해야 한다(같은 _check_role_detected 사용).
_PHASE_FINAL_ROLE_REVEAL = "final_role_reveal"
_PHASE_NIGHT_DOPPELGANGER = "night_doppelganger"
_PHASE_NIGHT_SEER = "night_seer"
_PHASE_NIGHT_INSOMNIAC = "night_insomniac"
_PHASE_NIGHT_ROBBER = "night_robber"
_PHASE_NIGHT_TROUBLEMAKER = "night_troublemaker"
_PHASE_NIGHT_DRUNK = "night_drunk"
# FSM은 투표를 VOTE_COUNTDOWN("vote_countdown")으로 진입시키고 전원 투표 전까지
# 여기 머문다. "vote"는 자동 전이 경로가 없는 사실상 死페이즈이므로, 포인팅 투표는
# 두 문자열 모두에서 감지해야 한다. 둘 다 expected_events=[VOTE_POINT]로 동일 처리됨.
_PHASE_VOTE = "vote"
_PHASE_VOTE_COUNTDOWN = "vote_countdown"

# YOLO cls_name (Title Case) → FSM role 문자열 (lowercase) 변환
_BACK_CLASS = "Card_Back"

# ── 감지 파라미터 ───────────────────────────────────────────────────────────────
_GRAB_DIST_THRESHOLD = 0.08   # 손목-카드 중심 최대 거리 (grab/release 판정)
_MIN_POINT_LENGTH = 0.03      # 손목→검지끝 최소 거리 (포인팅 제스처 판별)
_RAY_MAX_T = 1.5              # ray cast 최대 거리 (정규화)
# 투표: 손가락 ray 와 좌석 좌표 사이 허용 수직거리(정규화). 이 안에 들어오는
# 좌석 중 가장 가까운(ray 진행방향 t>0) 좌석을 지목 대상으로 본다.
_SEAT_POINT_PERP_DIST = 0.18

# 역할 등록 단계 전용 파라미터
_ROLE_REG_HAND_DIST = 0.12       # 손목-카드 중심 최대 거리 (현재 미사용).

# 역할 등록 전환(카드 내려놓기) 전용 파라미터
_PLACED_DOWN_STABLE_FRAMES = 10  # 후면 카드가 이 프레임 이상 안정돼야 감지 (frame_skip=2 기준 ≈ 1초)


class WerewolfRules:
    """늑대인간 비전 이벤트 후보 생성기.

    FusionEngine 이 instantiate 하지 않고,
    WerewolfVisionPipeline 에서 CardTracker 참조와 함께 생성해
    FusionEngine.register_werewolf_rules() 로 주입한다.
    """

    def __init__(self, card_tracker: CardTracker) -> None:
        self._card_tracker = card_tracker
        self._last_phase: str = ""
        # ROLE_DETECTED 중복 발화 방지: 이미 감지된 actor_id 집합
        self._reported_roles: set[str] = set()
        # CARD_PEEK 중복 발화 방지: (actor_id, card_owner_id, card_index)
        self._reported_peeks: set[tuple] = set()
        # CARD_SWAP 중복 발화 방지: (actor_id, id_a, id_b) — 두 id 정렬
        self._reported_swaps: set[tuple] = set()
        # CARD_SWAP 첫 번째 grab 기억: actor_id → (track_id, id_str)
        self._swap_first_touch: dict[str, tuple[int, str]] = {}
        # VOTE_POINT: voter_id → 이미 투표한 target_id (1인 1표)
        self._votes_cast: dict[str, str] = {}
        # 역할 등록 단계: 직전 active_player 추적 (플레이어 전환 감지용)
        self._last_reg_player: str = ""
        # 역할 등록 전환: 카드 안정 상태 추적 (stable↔unstable 전환 감지용)
        self._card_was_stable: bool = False

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
            self._reported_roles.clear()
            self._reported_peeks.clear()
            self._reported_swaps.clear()
            self._swap_first_touch.clear()
            self._votes_cast.clear()
            self._last_reg_player = ""
            self._card_was_stable = False

        tracked = self._card_tracker.get_tracked_cards()
        candidates: list[tuple[str, dict, float]] = []

        if phase == _PHASE_ROLE_REG_TRANSITION:
            c = self._check_card_placed_down(tracked)
            if c:
                candidates.append(c)

        elif phase in (_PHASE_ROLE_REGISTRATION, _PHASE_FINAL_ROLE_REVEAL):
            # 등록·최종 재확인 모두 active_player의 카드를 카메라로 재인식한다.
            # 플레이어가 전환되면 카드 stable_frames를 리셋해 재인식을 강제한다.
            # 직전 플레이어의 카드가 아직 테이블에 있을 경우 즉시 발화하는 연쇄 인식 방지.
            current_reg_player = ctx.active_player or ""
            if current_reg_player and current_reg_player != self._last_reg_player:
                self._last_reg_player = current_reg_player
                self._card_tracker.reset_stable_frames()
            c = self._check_role_detected(ctx, perception, tracked)
            if c:
                candidates.append(c)

        elif phase in (_PHASE_NIGHT_DOPPELGANGER, _PHASE_NIGHT_SEER, _PHASE_NIGHT_INSOMNIAC):
            c = self._check_card_peek(perception, ctx, tracked)
            if c:
                candidates.append(c)

        elif phase in (_PHASE_NIGHT_ROBBER, _PHASE_NIGHT_TROUBLEMAKER, _PHASE_NIGHT_DRUNK):
            c = self._check_card_swap(perception, ctx, tracked)
            if c:
                candidates.append(c)

        elif phase in (_PHASE_VOTE, _PHASE_VOTE_COUNTDOWN):
            for hand in perception.hands:
                c = self._check_vote_point(hand, ctx, tracked)
                if c:
                    candidates.append(c)

        return candidates

    # ── ROLE_DETECTED ────────────────────────────────────────────────────────────

    def _check_role_detected(
        self,
        ctx: FusionContext,
        perception: FramePerception,
        tracked: list[TrackedCard],
    ) -> tuple[str, dict, float] | None:
        """역할 등록 단계: 다음 조건을 모두 만족하는 카드가 있으면 ROLE_DETECTED 발화.

          1. face_up 이고 역할 클래스명이 확인된 카드 (Card_Back 제외)
          2. stable_frames >= 3 (frame_skip=2 기준 ≈ 0.3초 안정 인식)

        active_player(현재 등록 중인 플레이어)당 1회만 발화. 역할명은 소문자로 정규화.
        """
        actor_id = ctx.active_player
        if not actor_id or actor_id in self._reported_roles:
            return None
        for card in tracked:
            if not card.face_up:
                continue
            if card.cls_name is None or card.cls_name == _BACK_CLASS:
                continue
            if card.stable_frames < 2:
                continue
            # 다른 플레이어의 카드가 감지된 경우: card_player_id를 포함해 세션이 경고 처리
            self._reported_roles.add(actor_id)
            return (
                ROLE_DETECTED,
                {
                    "actor_id": actor_id,
                    "role": card.cls_name.lower(),
                    "card_player_id": card.player_id,
                },
                0.9,
            )
        return None

    def _check_card_placed_down(
        self,
        tracked: list[TrackedCard],
    ) -> tuple[str, dict, float] | None:
        """역할 등록 전환 단계: 카드 안정 상태 전환을 감지해 이벤트 발화.

        stable → unstable : CARD_UNSTABLE
        unstable → stable : CARD_PLACED_DOWN
        """
        is_stable = any(
            card.stable_frames >= _PLACED_DOWN_STABLE_FRAMES
            for card in tracked
        )
        if is_stable and not self._card_was_stable:
            self._card_was_stable = True
            return (CARD_PLACED_DOWN, {}, 0.9)
        if not is_stable and self._card_was_stable:
            self._card_was_stable = False
            return (CARD_UNSTABLE, {}, 0.9)
        return None

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
        """손목[0]→검지끝[8] ray 가 가장 잘 향하는 좌석(player)을 지목 → VOTE_POINT.

        카드 위치/인식과 무관하게 ctx.anchors 의 seat_{pid} 좌표로 사람을 가리킨다.
        투표 단계의 카드는 테이블 중앙에 모여 player_id=None 으로 잡히므로(카드 기반
        지목은 동작 불가), 좌석 좌표 ray 매칭으로 대체했다. 1인 1표.
        """
        voter_id = hand.player_id
        if not voter_id:
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

        # ctx.anchors 에서 seat_{pid} 좌표 수집 (자기 자신 제외)
        best_target: str | None = None
        best_perp = _SEAT_POINT_PERP_DIST
        for key, pos in ctx.anchors.items():
            if not key.startswith("seat_"):
                continue
            target_id = key[len("seat_"):]
            if target_id == voter_id:
                continue
            sx = pos.get("x")
            sy = pos.get("y")
            if sx is None or sy is None:
                continue
            # ray(wrist + t·(nx,ny)) 위로의 좌석 투영 파라미터 t.
            t = (sx - wrist[0]) * nx + (sy - wrist[1]) * ny
            if t <= 0 or t > _RAY_MAX_T:
                continue  # 손가락 뒤쪽 또는 너무 먼 좌석
            # ray 직선과 좌석점 사이 수직거리.
            proj_x = wrist[0] + t * nx
            proj_y = wrist[1] + t * ny
            perp = math.hypot(sx - proj_x, sy - proj_y)
            if perp < best_perp:
                best_perp = perp
                best_target = target_id

        if best_target is None:
            return None

        # 동일 대상 매 프레임 재발화 억제. 대상이 바뀐 경우만 발화.
        if best_target == self._votes_cast.get(voter_id):
            return None

        self._votes_cast[voter_id] = best_target
        data = {
            "actor_id": voter_id,
            "target_id": best_target,
            "_key": (voter_id, best_target),
        }
        return VOTE_POINT, data, 0.85


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

def _any_hand_near_card(
    hands: list[HandDet],
    bbox: object,
    threshold: float,
) -> bool:
    """어떤 손의 손목이라도 카드 중심(cx, cy) 으로부터 threshold 이내에 있으면 True.

    역할 등록 시 테이블에 놓인 카드(손 없음)와 손으로 집어든 카드를 구분한다.
    """
    for hand in hands:
        wx, wy = hand.wrist_xy
        if math.hypot(bbox.cx - wx, bbox.cy - wy) < threshold:
            return True
    return False


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
