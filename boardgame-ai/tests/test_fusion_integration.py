"""FusionEngine + YachtRules 통합 테스트.

Mock FramePerception + FusionContext로 3조건 필터와 이벤트 생성 검증.
"""

from __future__ import annotations

from core.constants import CommonEventType, CommonPhase, DEFAULT_PARAMS
from core.events import FusionContext
from vision.fusion.engine import FusionEngine
from vision.fusion.yacht_rules import DICE_ROLLED, DICE_STABLE, PHASE_WAITING_ROLL
from vision.schemas import BBox, DiceState, FramePerception, HandDet


# ── 픽스처 헬퍼 ───────────────────────────────────────────────────────────────

def _ctx_seat_right(player_id: str = "p_1") -> FusionContext:
    return FusionContext(
        fsm_state=CommonPhase.SEAT_REGISTER_RIGHT,
        game_type=None,
        active_player=player_id,
        allowed_actors=[player_id],
        expected_events=[CommonEventType.SEAT_HAND_REGISTERED],
        params={"gesture_stabilization_frames": 3},
    )


def _ctx_waiting_roll(player_id: str = "p_1") -> FusionContext:
    return FusionContext(
        fsm_state=PHASE_WAITING_ROLL,
        game_type="yacht",
        active_player=player_id,
        allowed_actors=[player_id],
        expected_events=[DICE_ROLLED, DICE_STABLE],
        params={"stabilization_frames": 3},
    )


def _v_sign_hand(wrist_xy: tuple[float, float] = (0.5, 0.5)) -> HandDet:
    return HandDet(
        handedness="Right",
        wrist_xy=wrist_xy,
        landmarks_21=[(0.0, 0.0)] * 21,
        gesture="v_sign",
        player_id="p_1",
    )


def _stable_dice(n: int = 5, pip: int = 3) -> list[DiceState]:
    bbox = BBox(0.1, 0.1, 0.2, 0.2, 0.9, "dice")
    return [
        DiceState(track_id=i, bbox=bbox, center=(0.15, 0.15),
                  motion_score=0.0001, stable_frames=10, pip_count=pip)
        for i in range(n)
    ]


def _frame(
    frame_id: int,
    hands: list[HandDet] | None = None,
    dice: list[DiceState] | None = None,
    roll_actor_id: str | None = None,
) -> FramePerception:
    return FramePerception(
        frame_id=frame_id,
        ts=float(frame_id) / 30.0,
        image_hw=(1080, 1920),
        hands=hands or [],
        dice=dice or [],
        roll_actor_id=roll_actor_id,
    )


# ── SEAT_REGISTER_RIGHT 테스트 ────────────────────────────────────────────────

def test_seat_hand_registered_after_stabilization() -> None:
    """V-sign 3프레임 유지 → seat_hand_registered 이벤트 발생."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_right())

    hand = _v_sign_hand()
    events = []
    for i in range(3):
        events = engine.feed(_frame(i, hands=[hand]))

    assert len(events) == 1
    e = events[0]
    assert e.event_type == CommonEventType.SEAT_HAND_REGISTERED
    assert e.data["hand"] == "Right"
    assert e.data["gesture"] == "v_sign"


def test_seat_hand_not_fired_before_stabilization() -> None:
    """V-sign 2프레임이면 이벤트 없음 (stabilization_frames=3)."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_right())

    hand = _v_sign_hand()
    all_events = []
    for i in range(2):
        all_events.extend(engine.feed(_frame(i, hands=[hand])))

    assert all_events == []


def test_wrong_gesture_not_fired() -> None:
    """OK-sign은 SEAT_REGISTER_RIGHT에서 이벤트 없음."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_right())

    ok_hand = HandDet(
        handedness="Right",
        wrist_xy=(0.5, 0.5),
        landmarks_21=[(0.0, 0.0)] * 21,
        gesture="ok_sign",
        player_id="p_1",
    )
    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, hands=[ok_hand])))

    assert all_events == []


def test_reject_event_not_fired() -> None:
    """reject_events에 있는 event_type은 발화 안 됨."""
    engine = FusionEngine()
    ctx = _ctx_seat_right()
    ctx.reject_events = [CommonEventType.SEAT_HAND_REGISTERED]
    engine.update_context(ctx)

    hand = _v_sign_hand()
    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, hands=[hand])))

    assert all_events == []


# ── WAITING_ROLL (요트) 테스트 ────────────────────────────────────────────────

def test_dice_rolled_event_emitted() -> None:
    """roll_actor_id + 5개 pip 확정 3프레임 → dice_rolled 이벤트."""
    engine = FusionEngine()
    engine.update_context(_ctx_waiting_roll())

    dice = _stable_dice(n=5, pip=4)
    all_events = []
    for i in range(3):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id="p_1")))

    rolled = [e for e in all_events if e.event_type == DICE_ROLLED]
    assert len(rolled) == 1
    e = rolled[0]
    assert e.actor_id == "p_1"
    assert e.data["dice_values"] == [4, 4, 4, 4, 4]


def test_dice_rolled_not_fired_without_actor() -> None:
    """roll_actor_id 없으면 dice_rolled 이벤트 없음."""
    engine = FusionEngine()
    engine.update_context(_ctx_waiting_roll())

    dice = _stable_dice(n=5, pip=2)
    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id=None)))

    rolled = [e for e in all_events if e.event_type == DICE_ROLLED]
    assert rolled == []


def test_dice_rolled_fired_with_partial_none_pip() -> None:
    """pip_count가 일부 None이어도 나머지가 인식됐으면 dice_rolled 이벤트 발생 (낮은 confidence)."""
    engine = FusionEngine()
    engine.update_context(_ctx_waiting_roll())

    dice = _stable_dice(n=5, pip=3)
    dice[2].pip_count = None  # 하나 미확정

    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id="p_1")))

    rolled = [e for e in all_events if e.event_type == DICE_ROLLED]
    assert len(rolled) == 1
    assert rolled[0].confidence < 0.9  # 부분 인식이므로 낮은 confidence

def test_dice_rolled_not_fired_with_all_none_pip() -> None:
    """pip_count가 전부 None이면 dice_rolled 이벤트 없음."""
    engine = FusionEngine()
    engine.update_context(_ctx_waiting_roll())

    dice = _stable_dice(n=5, pip=3)
    for d in dice:
        d.pip_count = None  # 전부 미확정

    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id="p_1")))

    rolled = [e for e in all_events if e.event_type == DICE_ROLLED]
    assert rolled == []


def test_context_switch_resets_counter() -> None:
    """FusionContext 전환 시 안정화 카운터 리셋 → 재차 stabilization 필요."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_right())

    hand = _v_sign_hand()
    # 2프레임 누적 후 context 전환
    engine.feed(_frame(0, hands=[hand]))
    engine.feed(_frame(1, hands=[hand]))

    # context 전환 → 카운터 리셋
    engine.update_context(_ctx_seat_right(player_id="p_2"))

    events = []
    # 1프레임만 더 → 아직 3프레임 안 됨
    events = engine.feed(_frame(2, hands=[hand]))
    assert events == []
