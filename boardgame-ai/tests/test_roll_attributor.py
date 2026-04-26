"""RollAttributor 시나리오 테스트 — 손 점유(occlusion) 기반.

핵심 흐름:
  WAITING → 손이 tray 진입 → HAND_IN_TRAY → 손 빠짐 + dice 5개 stable + 변화 → ROLL_CONFIRMED
"""

from __future__ import annotations

from vision.attribution.roll_attributor import RollAttributor, RollState
from vision.schemas import BBox, DiceState, FramePerception, HandDet


def _tray() -> BBox:
    return BBox(0.2, 0.2, 0.8, 0.8, 0.9, "tray")


def _tray_inner() -> BBox:
    return BBox(0.6, 0.2, 0.8, 0.8, 0.9, "tray_inner")


def _hand(player_id: str | None, wrist_xy: tuple[float, float]) -> HandDet:
    return HandDet(
        handedness="Right",
        wrist_xy=wrist_xy,
        landmarks_21=[wrist_xy] * 21,
        gesture=None,
        player_id=player_id,
    )


def _dice(track_id: int, center: tuple[float, float], pip: int | None) -> DiceState:
    cx, cy = center
    return DiceState(
        track_id=track_id,
        bbox=BBox(cx - 0.03, cy - 0.03, cx + 0.03, cy + 0.03, 0.9, "dice"),
        center=center,
        motion_score=0.0001,
        stable_frames=35,
        pip_count=pip,
    )


def _initial_dice() -> list[DiceState]:
    """굴림 전: tray 안 5개 안정."""
    return [_dice(i, (0.3 + 0.05 * i, 0.4), pip=2) for i in range(5)]


def _rolled_dice() -> list[DiceState]:
    """굴림 후: 위치/pip 모두 변경."""
    return [_dice(i, (0.32 + 0.06 * i, 0.5), pip=((i + 3) % 6) + 1) for i in range(5)]


def _frame(
    frame_id: int,
    hands: list[HandDet],
    dice: list[DiceState],
    tray_inner: BBox | None = None,
    roll_tray_in: bool = True,
) -> FramePerception:
    """기본적으로 roll_tray가 tray 안에 있다고 가정.

    roll_tray 진입 게이트 테스트를 위해 roll_tray_in=False로 설정 가능.
    """
    rt = (
        BBox(0.4, 0.4, 0.55, 0.55, 0.9, "roll_tray")
        if roll_tray_in
        else BBox(0.0, 0.0, 0.05, 0.05, 0.9, "roll_tray")
    )
    return FramePerception(
        frame_id=frame_id,
        ts=float(frame_id) / 30.0,
        image_hw=(1080, 1920),
        tray=_tray(),
        tray_inner=tray_inner,
        roll_tray=rt,
        dice=dice,
        hands=hands,
    )


# ── 테스트 ────────────────────────────────────────────────────────────────────


def test_normal_roll_player_a() -> None:
    """A 손이 tray 진입 → 빠진 후 dice 변화 + 안정 → ROLL_CONFIRMED."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )

    # WAITING — 초기 상태
    attr.update(_frame(0, [], _initial_dice()))
    assert attr.state == RollState.WAITING

    # A 손이 tray 진입 → HAND_IN_TRAY
    hand_in = _hand("p_a", (0.5, 0.5))
    attr.update(_frame(1, [hand_in], _initial_dice()))
    assert attr.state == RollState.HAND_IN_TRAY

    # 점유 유지
    attr.update(_frame(2, [hand_in], _initial_dice()))

    # 손이 빠지고 dice가 변화 + 안정 → 발화
    result = attr.update(_frame(3, [], _rolled_dice()))
    assert result == "p_a"
    assert attr.state == RollState.WAITING


def test_brief_touch_does_not_fire() -> None:
    """손은 들어왔다 나갔지만 dice 변화 없음 → 발화 안 함."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )
    initial = _initial_dice()

    attr.update(_frame(0, [], initial))
    attr.update(_frame(1, [_hand("p_a", (0.5, 0.5))], initial))
    assert attr.state == RollState.HAND_IN_TRAY

    # 손 빠짐 + dice 그대로 → 변화 점수 0 → 발화 없음
    result = attr.update(_frame(2, [], initial))
    assert result is None
    assert attr.state == RollState.WAITING


def test_two_consecutive_rolls() -> None:
    """연속 2회 굴림 — 각각 ROLL_CONFIRMED 발화."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )

    # 1차 굴림
    attr.update(_frame(0, [], _initial_dice()))
    attr.update(_frame(1, [_hand("p_a", (0.5, 0.5))], _initial_dice()))
    r1 = attr.update(_frame(2, [], _rolled_dice()))
    assert r1 == "p_a"

    # 2차 굴림 — 또 다른 위치/pip
    rolled2 = [_dice(i, (0.5 + 0.04 * i, 0.6), pip=((i * 2) % 6) + 1) for i in range(5)]
    attr.update(_frame(3, [_hand("p_a", (0.5, 0.5))], _rolled_dice()))
    r2 = attr.update(_frame(4, [], rolled2))
    assert r2 == "p_a"


def test_kept_dice_excluded_from_comparison() -> None:
    """tray_inner(킵존) 안에 있는 dice는 굴림 대상에서 제외 — 일부 굴림 시나리오."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )

    # 5개 중 2개는 킵존(x>=0.6), 3개는 굴림 영역(x<0.6)
    initial = [
        _dice(0, (0.3, 0.4), pip=1),
        _dice(1, (0.4, 0.4), pip=2),
        _dice(2, (0.5, 0.4), pip=3),
        _dice(3, (0.7, 0.4), pip=4),  # 킵존
        _dice(4, (0.75, 0.5), pip=5),  # 킵존
    ]
    keep = _tray_inner()

    attr.update(_frame(0, [], initial, tray_inner=keep))
    attr.update(_frame(1, [_hand("p_a", (0.4, 0.5))], initial, tray_inner=keep))
    assert attr.state == RollState.HAND_IN_TRAY

    # 굴림 후 — 킵존 외 3개만 변경, 킵존 2개는 그대로
    rolled = [
        _dice(0, (0.32, 0.5), pip=6),  # 변화
        _dice(1, (0.42, 0.5), pip=5),  # 변화
        _dice(2, (0.52, 0.5), pip=4),  # 변화
        _dice(3, (0.7, 0.4), pip=4),  # 그대로 (킵존)
        _dice(4, (0.75, 0.5), pip=5),  # 그대로 (킵존)
    ]
    result = attr.update(_frame(2, [], rolled, tray_inner=keep))
    assert result == "p_a"


def test_finger_in_tray_triggers_occupation() -> None:
    """wrist는 밖이지만 손가락 끝이 tray 안이어도 점유로 인정."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )
    attr.update(_frame(0, [], _initial_dice()))

    # wrist는 tray 밖, 그러나 검지 끝(landmark[8])이 안에
    finger_hand = HandDet(
        handedness="Right",
        wrist_xy=(0.05, 0.5),  # 밖
        landmarks_21=[(0.05, 0.5)] * 8 + [(0.5, 0.5)] + [(0.05, 0.5)] * 12,
        gesture=None,
        player_id="p_a",
    )
    attr.update(_frame(1, [finger_hand], _initial_dice()))
    assert attr.state == RollState.HAND_IN_TRAY


def test_no_tray_no_occupation() -> None:
    """tray 미감지면 점유 판정 안 함."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )
    perception = FramePerception(
        frame_id=0,
        ts=0.0,
        image_hw=(1080, 1920),
        tray=None,
        dice=_initial_dice(),
        hands=[_hand("p_a", (0.5, 0.5))],
    )
    result = attr.update(perception)
    assert result is None
    assert attr.state == RollState.WAITING


def test_static_scene_no_fire() -> None:
    """손도 없고 dice 변화도 없으면 영원히 WAITING — 발화 없음."""
    attr = RollAttributor(
        stabilization_frames=3,
        enter_debounce_frames=1,
        exit_debounce_frames=1,
        roll_tray_in_tray_required=1,
    )
    for i in range(20):
        result = attr.update(_frame(i, [], _initial_dice()))
        assert result is None
    assert attr.state == RollState.WAITING
