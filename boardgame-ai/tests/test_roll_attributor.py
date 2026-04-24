"""RollAttributor 시나리오 테스트.

실제 카메라 없이 FramePerception 시퀀스를 수동으로 구성해 검증.
"""

from __future__ import annotations

from vision.attribution.roll_attributor import RollAttributor, RollState
from vision.schemas import BBox, DiceState, FramePerception, HandDet


# ── 픽스처 헬퍼 ───────────────────────────────────────────────────────────────

def _bbox(x1=0.3, y1=0.3, x2=0.7, y2=0.7) -> BBox:
    return BBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=0.9, cls_name="roll_tray")


def _hand(
    player_id: str | None,
    gesture: str,
    wrist_xy: tuple[float, float] = (0.5, 0.5),
    handedness: str = "Right",
) -> HandDet:
    return HandDet(
        handedness=handedness,
        wrist_xy=wrist_xy,
        landmarks_21=[(0.0, 0.0)] * 21,
        gesture=gesture,
        player_id=player_id,
    )


def _stable_dice(n: int = 5, stable_frames: int = 35, pip: int = 3) -> list[DiceState]:
    bbox = BBox(0.1, 0.1, 0.2, 0.2, 0.9, "dice")
    return [
        DiceState(track_id=i, bbox=bbox, center=(0.15, 0.15),
                  motion_score=0.0001, stable_frames=stable_frames, pip_count=pip)
        for i in range(n)
    ]


def _moving_dice(n: int = 5) -> list[DiceState]:
    bbox = BBox(0.1, 0.1, 0.2, 0.2, 0.9, "dice")
    return [
        DiceState(track_id=i, bbox=bbox, center=(0.15, 0.15),
                  motion_score=0.05, stable_frames=0, pip_count=None)
        for i in range(n)
    ]


def _frame(
    frame_id: int,
    hands: list[HandDet],
    dice: list[DiceState],
    roll_tray: BBox | None = None,
    tray_inner: BBox | None = None,
) -> FramePerception:
    rt = roll_tray or _bbox()
    return FramePerception(
        frame_id=frame_id,
        ts=float(frame_id) / 30.0,
        image_hw=(1080, 1920),
        roll_tray=rt,
        tray_inner=tray_inner or BBox(0.2, 0.2, 0.8, 0.8, 0.9, "tray_inner"),
        dice=dice,
        hands=hands,
    )


# ── 테스트 ────────────────────────────────────────────────────────────────────

def test_normal_roll_player_a() -> None:
    """Player A 정상 굴림 → roll_actor_id == 'p_a'."""
    attr = RollAttributor(stabilization_frames=3)

    # IDLE: grab 없음
    result = attr.update(_frame(0, [], _moving_dice()))
    assert result is None
    assert attr.state == RollState.IDLE

    # GRAB_SEEN: A가 roll_tray 위에서 grab
    result = attr.update(_frame(1, [_hand("p_a", "grab", (0.5, 0.5))], _moving_dice()))
    assert result is None
    assert attr.state == RollState.GRAB_SEEN

    # ROLL_TRAY_LIFTED: roll_tray 위치 이동
    moved_rt = _bbox(0.32, 0.32, 0.72, 0.72)  # lift_speed > 0.01
    result = attr.update(_frame(2, [_hand("p_a", "grab", (0.5, 0.5))], _moving_dice(), roll_tray=moved_rt))
    assert result is None
    assert attr.state == RollState.ROLL_TRAY_LIFTED

    # RELEASE_SEEN
    result = attr.update(_frame(3, [_hand("p_a", "release", (0.5, 0.5))], _moving_dice()))
    assert result is None
    assert attr.state == RollState.RELEASE_SEEN

    # DICE_MOVING
    result = attr.update(_frame(4, [], _moving_dice()))
    assert result is None
    assert attr.state == RollState.DICE_MOVING

    # DICE_STABLE → 확정
    result = attr.update(_frame(5, [], _stable_dice(stable_frames=5)))
    assert result == "p_a"
    assert attr.state == RollState.DICE_STABLE

    # 다음 프레임에서 IDLE로 리셋
    attr.update(_frame(6, [], _stable_dice()))
    assert attr.state == RollState.IDLE


def test_brief_touch_does_not_change_actor() -> None:
    """Player B가 중간에 잠깐 트레이 건드려도 actor는 A."""
    attr = RollAttributor(stabilization_frames=3)

    # A grab
    attr.update(_frame(0, [_hand("p_a", "grab", (0.5, 0.5))], _moving_dice()))
    assert attr.state == RollState.GRAB_SEEN

    # B가 잠깐 grab (A grab 유지)
    both = [_hand("p_a", "grab", (0.5, 0.5)), _hand("p_b", "grab", (0.6, 0.6))]
    attr.update(_frame(1, both, _moving_dice()))

    # A release
    attr.update(_frame(2, [_hand("p_a", "release", (0.5, 0.5))], _moving_dice()))
    attr.update(_frame(3, [], _moving_dice()))
    result = attr.update(_frame(4, [], _stable_dice(stable_frames=5)))
    assert result == "p_a"


def test_fallback_when_no_grab_detected() -> None:
    """grab 인식 실패 → fallback: roll_tray 근처에 오래 있던 손 player_id."""
    attr = RollAttributor(stabilization_frames=3, grab_fallback_window_frames=10)

    # grab 없이 neutral 손만 있는 프레임 여러 개
    for i in range(8):
        attr.update(_frame(i, [_hand("p_c", "neutral", (0.5, 0.5))], _moving_dice()))

    # dice_moving → stable
    attr.update(_frame(8, [], _moving_dice()))
    result = attr.update(_frame(9, [], _stable_dice(stable_frames=5)))
    # fallback: p_c가 roll_tray 근처에 계속 있었으므로 p_c
    assert result == "p_c"


def test_no_dice_no_actor() -> None:
    """주사위가 없으면 actor 확정 없음."""
    attr = RollAttributor(stabilization_frames=3)
    for i in range(10):
        result = attr.update(_frame(i, [], []))
    assert result is None
    assert attr.state == RollState.IDLE
