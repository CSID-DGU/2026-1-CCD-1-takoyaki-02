"""FusionEngine + YachtRules 통합 테스트.

Mock FramePerception + FusionContext로 3조건 필터와 이벤트 생성 검증.
"""

from __future__ import annotations

from core.constants import CommonEventType, CommonPhase
from core.events import FusionContext
from vision.fusion.engine import FusionEngine
from vision.fusion.yacht_rules import (
    DICE_ESCAPED,
    PHASE_AWAITING_ROLL,
    ROLL_CONFIRMED,
    ROLL_UNREADABLE,
)
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


def _ctx_awaiting_roll(player_id: str = "p_1") -> FusionContext:
    return FusionContext(
        fsm_state=PHASE_AWAITING_ROLL,
        game_type="yacht",
        active_player=player_id,
        allowed_actors=[player_id],
        expected_events=[ROLL_CONFIRMED, ROLL_UNREADABLE, DICE_ESCAPED],
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
        DiceState(
            track_id=i,
            bbox=bbox,
            center=(0.15, 0.15),
            motion_score=0.0001,
            stable_frames=10,
            pip_count=pip,
        )
        for i in range(n)
    ]


def _frame(
    frame_id: int,
    hands: list[HandDet] | None = None,
    dice: list[DiceState] | None = None,
    roll_actor_id: str | None = None,
    tray: BBox | None = None,
    roll_just_confirmed: bool = False,
) -> FramePerception:
    return FramePerception(
        frame_id=frame_id,
        ts=float(frame_id) / 30.0,
        image_hw=(1080, 1920),
        hands=hands or [],
        dice=dice or [],
        roll_actor_id=roll_actor_id,
        tray=tray,
        roll_just_confirmed=roll_just_confirmed,
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


# ── AWAITING_ROLL (요트) 테스트 ───────────────────────────────────────────────


def test_dice_rolled_event_emitted() -> None:
    """roll_actor_id + 5개 pip 확정 3프레임 → ROLL_CONFIRMED 이벤트."""
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    dice = _stable_dice(n=5, pip=4)
    # ROLL_CONFIRMED는 RollAttributor가 게이트 통과시킨 1회성 신호 — FusionEngine에서 즉시 발화
    events = engine.feed(_frame(0, dice=dice, roll_actor_id="p_1", roll_just_confirmed=True))
    rolled = [e for e in events if e.event_type == ROLL_CONFIRMED]
    assert len(rolled) == 1
    e = rolled[0]
    assert e.actor_id == "p_1"
    assert e.data["dice_values"] == [4, 4, 4, 4, 4]


def test_dice_rolled_not_fired_without_actor() -> None:
    """roll_actor_id도 없고 ctx.active_player도 없으면 ROLL_CONFIRMED 이벤트 없음."""
    engine = FusionEngine()
    ctx_no_actor = FusionContext(
        fsm_state=PHASE_AWAITING_ROLL,
        game_type="yacht",
        active_player=None,
        allowed_actors=[],
        expected_events=[ROLL_CONFIRMED],
    )
    engine.update_context(ctx_no_actor)

    dice = _stable_dice(n=5, pip=2)
    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id=None)))

    rolled = [e for e in all_events if e.event_type == ROLL_CONFIRMED]
    assert rolled == []


def test_partial_pip_fires_roll_unreadable() -> None:
    """pip_count가 일부 None이면 ROLL_CONFIRMED 대신 ROLL_UNREADABLE 발화."""
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    dice = _stable_dice(n=5, pip=3)
    dice[2].pip_count = None

    events = engine.feed(_frame(0, dice=dice, roll_actor_id="p_1", roll_just_confirmed=True))
    confirmed = [e for e in events if e.event_type == ROLL_CONFIRMED]
    unreadable = [e for e in events if e.event_type == ROLL_UNREADABLE]
    assert confirmed == []
    assert len(unreadable) == 1
    e = unreadable[0]
    assert e.actor_id == "p_1"
    assert e.data["unknown_indices"] == [2]
    assert e.confidence < 0.9


def test_dice_rolled_not_fired_with_all_none_pip() -> None:
    """pip_count가 전부 None이면 ROLL_CONFIRMED 이벤트 없음."""
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    dice = _stable_dice(n=5, pip=3)
    for d in dice:
        d.pip_count = None

    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id="p_1")))

    rolled = [e for e in all_events if e.event_type == ROLL_CONFIRMED]
    assert rolled == []


def test_context_switch_resets_counter() -> None:
    """FusionContext 전환 시 안정화 카운터 리셋 → 재차 stabilization 필요."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_right())

    hand = _v_sign_hand()
    engine.feed(_frame(0, hands=[hand]))
    engine.feed(_frame(1, hands=[hand]))

    engine.update_context(_ctx_seat_right(player_id="p_2"))

    events = engine.feed(_frame(2, hands=[hand]))
    assert events == []


# ── DICE_ESCAPED ──────────────────────────────────────────────────────────────


def _tray_bbox() -> BBox:
    return BBox(0.2, 0.2, 0.8, 0.8, 0.9, "tray")


def _dice_at(track_id: int, center: tuple[float, float], pip: int = 3) -> DiceState:
    cx, cy = center
    return DiceState(
        track_id=track_id,
        bbox=BBox(cx - 0.02, cy - 0.02, cx + 0.02, cy + 0.02, 0.9, "dice"),
        center=center,
        motion_score=0.0001,
        stable_frames=10,
        pip_count=pip,
    )


def test_dice_escaped_fires_when_dice_outside_tray() -> None:
    """tray 안에 있던 주사위가 밖으로 나가면 DICE_ESCAPED 발화."""
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    tray = _tray_bbox()
    inside = _dice_at(1, (0.5, 0.5))
    # track_id=2가 처음엔 안에 있다가 밖으로 나가는 시나리오
    started_inside = _dice_at(2, (0.5, 0.6))
    moved_outside = _dice_at(2, (0.95, 0.5))

    all_events = []
    # 먼저 안에 있는 상태로 _seen_inside 등록
    for i in range(2):
        all_events.extend(
            engine.feed(_frame(i, dice=[inside, started_inside], roll_actor_id="p_1", tray=tray))
        )
    # 그 다음 track_id=2가 밖으로
    for i in range(2, 7):
        all_events.extend(
            engine.feed(_frame(i, dice=[inside, moved_outside], roll_actor_id="p_1", tray=tray))
        )

    escaped = [e for e in all_events if e.event_type == DICE_ESCAPED]
    assert len(escaped) == 1
    assert escaped[0].data["escaped_track_ids"] == [2]


def test_dice_escaped_not_fired_when_tray_missing() -> None:
    """tray 감지가 없으면 DICE_ESCAPED 발화 안 함 (오탐 방지)."""
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    outside = _dice_at(1, (0.95, 0.5))
    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=[outside], roll_actor_id="p_1", tray=None)))

    escaped = [e for e in all_events if e.event_type == DICE_ESCAPED]
    assert escaped == []


def test_dice_escaped_not_fired_when_all_dice_inside() -> None:
    engine = FusionEngine()
    engine.update_context(_ctx_awaiting_roll())

    tray = _tray_bbox()
    dice = [_dice_at(i + 1, (0.4 + 0.05 * i, 0.5)) for i in range(3)]

    all_events = []
    for i in range(5):
        all_events.extend(engine.feed(_frame(i, dice=dice, roll_actor_id="p_1", tray=tray)))

    escaped = [e for e in all_events if e.event_type == DICE_ESCAPED]
    assert escaped == []


# ── SEAT_REGISTER (단일 phase, 오른손 V → 왼손 OK 순차) 테스트 ────────────────


def _ctx_seat_register(player_id: str = "p_1") -> FusionContext:
    return FusionContext(
        fsm_state=CommonPhase.SEAT_REGISTER,
        game_type=None,
        active_player=player_id,
        allowed_actors=[player_id],
        expected_events=[
            CommonEventType.SEAT_RIGHT_REGISTERED,
            CommonEventType.SEAT_REGISTERED,
        ],
        params={"gesture_stabilization_frames": 3},
    )


def _hand_with_landmarks(handedness: str, gesture: str, wrist=(0.5, 0.7)):
    """arm_angle 계산을 위해 wrist(0)와 middle_mcp(9) 좌표를 의미 있게 채운다."""
    lms = [(0.0, 0.0)] * 21
    lms[0] = wrist
    lms[9] = (wrist[0], wrist[1] - 0.2)  # mcp가 wrist보다 위 → arm_angle ≈ +π/2
    return HandDet(
        handedness=handedness,
        wrist_xy=wrist,
        landmarks_21=lms,
        gesture=gesture,
    )


def test_seat_register_right_event_fires_on_v_sign() -> None:
    """오른손 V사인 N프레임 안정화 → seat_right_registered 1회 발화."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_register())

    right = _hand_with_landmarks("Right", "v_sign", wrist=(0.55, 0.7))
    events: list = []
    for i in range(3):
        events = engine.feed(_frame(i, hands=[right]))

    right_evts = [e for e in events if e.event_type == CommonEventType.SEAT_RIGHT_REGISTERED]
    assert len(right_evts) == 1
    assert right_evts[0].actor_id == "p_1"
    assert right_evts[0].data.get("hand") == "Right"


def test_seat_register_right_event_fires_only_once() -> None:
    """오른손 V사인이 계속 보여도 SEAT_RIGHT_REGISTERED는 actor당 1회만 발화."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_register())

    right = _hand_with_landmarks("Right", "v_sign", wrist=(0.55, 0.7))
    all_evts: list = []
    for i in range(10):
        all_evts.extend(engine.feed(_frame(i, hands=[right])))

    right_evts = [e for e in all_evts if e.event_type == CommonEventType.SEAT_RIGHT_REGISTERED]
    assert len(right_evts) == 1, f"중복 발화: {len(right_evts)}건"


def test_seat_registered_requires_right_first() -> None:
    """오른손 V사인 없이 왼손 OK사인만 보이면 seat_registered 발화 안 됨."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_register())

    left = _hand_with_landmarks("Left", "ok_sign", wrist=(0.45, 0.7))
    all_evts: list = []
    for i in range(5):
        all_evts.extend(engine.feed(_frame(i, hands=[left])))

    completed = [e for e in all_evts if e.event_type == CommonEventType.SEAT_REGISTERED]
    assert completed == []


def test_seat_registered_fires_after_sequential_v_then_ok() -> None:
    """오른손 V사인 통과 → 왼손 OK사인 통과 → seat_registered 발화 + seat_zone 페이로드."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_register())

    right = _hand_with_landmarks("Right", "v_sign", wrist=(0.55, 0.7))
    left = _hand_with_landmarks("Left", "ok_sign", wrist=(0.45, 0.7))

    # Step 1: 오른손 V사인 stab 통과
    for i in range(3):
        engine.feed(_frame(i, hands=[right]))

    # Step 2: 왼손 OK사인 stab 통과
    events: list = []
    for i in range(3, 6):
        events = engine.feed(_frame(i, hands=[left]))

    completed = [e for e in events if e.event_type == CommonEventType.SEAT_REGISTERED]
    assert len(completed) == 1
    payload = completed[0].data
    assert "seat_zone" in payload
    sz = payload["seat_zone"]
    assert "right_arm" in sz and "left_arm" in sz
    assert "body_xy" in sz and "posture" in sz
    assert sz["posture"] in ("stretched", "bent")


def test_seat_register_state_resets_on_phase_change() -> None:
    """다른 phase로 전환 시 _seat_right_confirmed/카운터 모두 초기화."""
    engine = FusionEngine()
    engine.update_context(_ctx_seat_register())

    right = _hand_with_landmarks("Right", "v_sign", wrist=(0.55, 0.7))
    for i in range(3):
        engine.feed(_frame(i, hands=[right]))

    # 다른 phase로 전환했다가 다시 SEAT_REGISTER로 돌아옴
    engine.update_context(_ctx_awaiting_roll())
    engine.update_context(_ctx_seat_register())

    # 오른손 정보가 초기화되었으므로 왼손 OK사인만으론 seat_registered 발화 X
    left = _hand_with_landmarks("Left", "ok_sign", wrist=(0.45, 0.7))
    all_evts: list = []
    for i in range(5):
        all_evts.extend(engine.feed(_frame(100 + i, hands=[left])))

    completed = [e for e in all_evts if e.event_type == CommonEventType.SEAT_REGISTERED]
    assert completed == []
