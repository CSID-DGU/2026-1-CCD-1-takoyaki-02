"""WerewolfRules 단위 테스트 — ROLE_DETECTED 감지 조건 검증.

검증 항목:
  - face_up + bbox 크기 + 손 근접 + stable_frames 모두 충족 시 발화
  - 조건별 개별 실패 케이스 (손 없음 / 손 너무 멀리 / bbox 너무 작음 / stable_frames 부족)
  - Card_Back / face_down 무시
  - 동일 플레이어 중복 발화 방지
  - active_player 전환 시 stable_frames 리셋 (연쇄 인식 방지)
  - CardTracker.reset_stable_frames 단위 동작
"""

from __future__ import annotations

from core.events import FusionContext
from vision.fusion.werewolf_rules import ROLE_DETECTED, WerewolfRules
from vision.schemas import BBox, FramePerception, HandDet
from vision.tracking.card_tracker import CardTracker
from vision.werewolf.schemas import TrackedCard


# ── 픽스처 헬퍼 ────────────────────────────────────────────────────────────────


def _ctx_role_reg(player_id: str = "p_1") -> FusionContext:
    return FusionContext(
        fsm_state="role_registration",
        game_type="werewolf",
        active_player=player_id,
        allowed_actors=[player_id],
        expected_events=[ROLE_DETECTED],
    )


def _card(
    cls_name: str = "Seer",
    face_up: bool = True,
    stable_frames: int = 15,
    bbox_cx: float = 0.45,
    bbox_cy: float = 0.45,
    bbox_w: float = 0.15,
    bbox_h: float = 0.20,
    track_id: int = 1,
) -> TrackedCard:
    x1 = bbox_cx - bbox_w / 2
    y1 = bbox_cy - bbox_h / 2
    return TrackedCard(
        track_id=track_id,
        bbox=BBox(x1, y1, x1 + bbox_w, y1 + bbox_h, 0.9, cls_name),
        cls_name=cls_name,
        face_up=face_up,
        player_id="p_1",
        card_index=0,
        stable_frames=stable_frames,
    )


def _hand_at(cx: float = 0.45, cy: float = 0.45) -> HandDet:
    return HandDet(
        handedness="Right",
        wrist_xy=(cx, cy),
        landmarks_21=[(0.0, 0.0)] * 21,
        gesture="neutral",
        player_id="p_1",
    )


def _frame(hands: list[HandDet] | None = None) -> FramePerception:
    return FramePerception(
        frame_id=0, ts=0.0, image_hw=(1080, 1920), hands=hands or []
    )


class _MockTracker:
    """CardTracker 스텁 — 주입된 카드 목록을 반환하고 reset 호출 횟수를 기록한다."""

    def __init__(self, cards: list[TrackedCard] | None = None) -> None:
        self._cards: list[TrackedCard] = cards or []
        self.reset_called_count: int = 0

    def get_tracked_cards(self) -> list[TrackedCard]:
        return self._cards

    def reset_stable_frames(self) -> None:
        self.reset_called_count += 1
        for card in self._cards:
            card.stable_frames = 0
            card.just_flipped_up = False


# ── ROLE_DETECTED 기본 발화 조건 ────────────────────────────────────────────────


def test_role_detected_happy_path() -> None:
    """face_up + 충분한 bbox + 손 근접 + stable_frames >= 15 → ROLE_DETECTED 발화."""
    tracker = _MockTracker([_card()])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at(0.45, 0.45)])

    result = rules._check_role_detected(ctx, perception, tracker.get_tracked_cards())

    assert result is not None
    event_type, data, conf = result
    assert event_type == ROLE_DETECTED
    assert data["actor_id"] == "p_1"
    assert data["role"] == "seer"
    assert conf > 0


def test_role_detected_no_hand_blocks() -> None:
    """손이 없으면 발화 안 됨."""
    tracker = _MockTracker([_card()])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_hand_too_far_blocks() -> None:
    """손목이 카드 중심에서 0.12 초과이면 발화 안 됨."""
    tracker = _MockTracker([_card(bbox_cx=0.45, bbox_cy=0.45)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    far_hand = _hand_at(cx=0.90, cy=0.45)  # 거리 ≈ 0.45 >> 0.12

    perception = _frame(hands=[far_hand])
    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_small_bbox_blocks() -> None:
    """bbox 단변 < 0.06 이면 발화 안 됨 (테이블에 놓인 멀리 있는 카드)."""
    small_card = _card(bbox_w=0.04, bbox_h=0.05)  # min(0.04, 0.05) = 0.04 < 0.06
    tracker = _MockTracker([small_card])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_bbox_exactly_at_threshold_passes() -> None:
    """bbox 단변 == 0.06 이면 발화됨 (경계값)."""
    threshold_card = _card(bbox_w=0.06, bbox_h=0.10)
    tracker = _MockTracker([threshold_card])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is not None


def test_role_detected_insufficient_stable_frames() -> None:
    """stable_frames < 15 이면 발화 안 됨."""
    tracker = _MockTracker([_card(stable_frames=14)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_exactly_15_stable_frames_passes() -> None:
    """stable_frames == 15 이면 발화됨 (경계값)."""
    tracker = _MockTracker([_card(stable_frames=15)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is not None


def test_role_detected_card_back_cls_ignored() -> None:
    """cls_name=Card_Back 은 face_up 이어도 발화 안 됨."""
    tracker = _MockTracker([_card(cls_name="Card_Back", face_up=True)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_face_down_ignored() -> None:
    """face_down 카드는 발화 안 됨."""
    tracker = _MockTracker([_card(cls_name="Seer", face_up=False, stable_frames=20)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg()
    perception = _frame(hands=[_hand_at()])

    assert rules._check_role_detected(ctx, perception, tracker.get_tracked_cards()) is None


def test_role_detected_fires_only_once_per_player() -> None:
    """같은 플레이어는 1회만 발화 (중복 방지)."""
    tracker = _MockTracker([_card()])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg("p_1")
    perception = _frame(hands=[_hand_at()])

    r1 = rules._check_role_detected(ctx, perception, tracker.get_tracked_cards())
    r2 = rules._check_role_detected(ctx, perception, tracker.get_tracked_cards())

    assert r1 is not None
    assert r2 is None


# ── active_player 전환 → stable_frames 리셋 ──────────────────────────────────


def test_player_change_triggers_reset_stable_frames() -> None:
    """build_candidates에서 active_player 전환 감지 시 reset_stable_frames 호출."""
    card = _card(stable_frames=20)
    tracker = _MockTracker([card])
    rules = WerewolfRules(tracker)
    perception = _frame(hands=[_hand_at()])

    # p1 첫 진입
    rules.build_candidates(_ctx_role_reg("p_1"), perception)
    assert tracker.reset_called_count == 1

    # p2로 전환
    rules.build_candidates(_ctx_role_reg("p_2"), perception)
    assert tracker.reset_called_count == 2
    assert card.stable_frames == 0  # 리셋 확인


def test_same_player_no_extra_reset() -> None:
    """같은 active_player가 유지되는 동안 reset은 최초 진입 1회만."""
    tracker = _MockTracker([_card(stable_frames=20)])
    rules = WerewolfRules(tracker)
    ctx = _ctx_role_reg("p_1")
    perception = _frame(hands=[_hand_at()])

    for _ in range(5):
        rules.build_candidates(ctx, perception)

    assert tracker.reset_called_count == 1


def test_phase_change_clears_last_reg_player() -> None:
    """페이즈 전환 후 같은 플레이어가 다시 role_registration에 진입하면 리셋 발생."""
    tracker = _MockTracker([_card(stable_frames=20)])
    rules = WerewolfRules(tracker)
    perception = _frame(hands=[_hand_at()])

    # p1 역할 등록
    rules.build_candidates(_ctx_role_reg("p_1"), perception)
    assert tracker.reset_called_count == 1

    # 다른 페이즈로 전환
    other_ctx = FusionContext(
        fsm_state="night_start",
        game_type="werewolf",
        active_player=None,
        allowed_actors=[],
        expected_events=[],
    )
    rules.build_candidates(other_ctx, perception)

    # 다시 role_registration으로 p1 진입 → _last_reg_player가 초기화됐으므로 리셋
    rules.build_candidates(_ctx_role_reg("p_1"), perception)
    assert tracker.reset_called_count == 2


# ── CardTracker.reset_stable_frames 단위 테스트 ───────────────────────────────


def test_card_tracker_reset_stable_frames_clears_all_cards() -> None:
    """reset_stable_frames 호출 후 모든 카드의 stable_frames=0, just_flipped_up=False."""
    real_tracker = CardTracker()
    real_tracker._card_states[1] = TrackedCard(
        track_id=1,
        bbox=BBox(0.3, 0.3, 0.6, 0.6, 0.9, "Seer"),
        cls_name="Seer",
        face_up=True,
        player_id="p_1",
        card_index=0,
        stable_frames=30,
        just_flipped_up=True,
    )
    real_tracker._card_states[2] = TrackedCard(
        track_id=2,
        bbox=BBox(0.1, 0.1, 0.3, 0.3, 0.8, "Werewolf"),
        cls_name="Werewolf",
        face_up=True,
        player_id="p_2",
        card_index=0,
        stable_frames=50,
        just_flipped_up=False,
    )

    real_tracker.reset_stable_frames()

    for card in real_tracker.get_tracked_cards():
        assert card.stable_frames == 0
        assert card.just_flipped_up is False


def test_card_tracker_reset_stable_frames_empty_tracker() -> None:
    """카드가 없을 때 reset_stable_frames 호출해도 오류 없음."""
    real_tracker = CardTracker()
    real_tracker.reset_stable_frames()  # 예외 없이 통과
    assert real_tracker.get_tracked_cards() == []
