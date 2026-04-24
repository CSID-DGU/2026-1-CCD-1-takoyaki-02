"""FramePerception 직렬화/역직렬화 계약 테스트."""

from __future__ import annotations

import json

from vision.schemas import BBox, DiceState, FramePerception, HandDet, YoloDet


def _make_bbox() -> BBox:
    return BBox(x1=0.1, y1=0.2, x2=0.5, y2=0.6, conf=0.9, cls_name="dice")


def _make_frame() -> FramePerception:
    bbox = _make_bbox()
    dice = DiceState(
        track_id=1,
        bbox=bbox,
        center=(0.3, 0.4),
        motion_score=0.001,
        stable_frames=31,
        pip_count=3,
    )
    hand = HandDet(
        handedness="Right",
        wrist_xy=(0.5, 0.7),
        landmarks_21=[(float(i) * 0.01, float(i) * 0.02) for i in range(21)],
        gesture="v_sign",
        player_id="p_abc123",
    )
    tray = BBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0, conf=0.95, cls_name="tray")
    return FramePerception(
        frame_id=42,
        ts=1234567890.0,
        image_hw=(1080, 1920),
        tray=tray,
        tray_inner=None,
        roll_tray=BBox(x1=0.3, y1=0.3, x2=0.7, y2=0.7, conf=0.88, cls_name="roll_tray"),
        dice=[dice],
        hands=[hand],
        roll_actor_id="p_abc123",
        phase_hints={"dice_all_stable": True, "dice_count": 1},
    )


# ── BBox ──────────────────────────────────────────────────────────────────────


def test_bbox_properties() -> None:
    b = BBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8, conf=0.9, cls_name="tray")
    assert abs(b.cx - 0.3) < 1e-9
    assert abs(b.cy - 0.5) < 1e-9
    assert abs(b.w - 0.4) < 1e-9
    assert abs(b.h - 0.6) < 1e-9


def test_bbox_iou_identical() -> None:
    b = _make_bbox()
    assert abs(b.iou(b) - 1.0) < 1e-6


def test_bbox_iou_no_overlap() -> None:
    a = BBox(0.0, 0.0, 0.3, 0.3, 0.9, "tray")
    b = BBox(0.5, 0.5, 1.0, 1.0, 0.9, "tray")
    assert b.iou(a) == 0.0


def test_bbox_contains_point() -> None:
    b = _make_bbox()
    assert b.contains_point(0.3, 0.4)
    assert not b.contains_point(0.0, 0.0)


def test_bbox_roundtrip() -> None:
    b = _make_bbox()
    assert BBox.from_dict(b.to_dict()) == b


# ── YoloDet ───────────────────────────────────────────────────────────────────


def test_yolo_det_roundtrip() -> None:
    det = YoloDet(cls_name="dice", bbox=_make_bbox(), track_id=7)
    assert YoloDet.from_dict(det.to_dict()) == det


def test_yolo_det_no_track_id() -> None:
    det = YoloDet(cls_name="tray", bbox=_make_bbox())
    restored = YoloDet.from_dict(det.to_dict())
    assert restored.track_id is None


# ── DiceState ─────────────────────────────────────────────────────────────────


def test_dice_state_roundtrip() -> None:
    ds = DiceState(
        track_id=3,
        bbox=_make_bbox(),
        center=(0.3, 0.4),
        motion_score=0.001,
        stable_frames=25,
        pip_count=5,
    )
    assert DiceState.from_dict(ds.to_dict()) == ds


def test_dice_state_no_pip() -> None:
    ds = DiceState(
        track_id=1, bbox=_make_bbox(), center=(0.3, 0.4), motion_score=0.01, stable_frames=2
    )
    assert DiceState.from_dict(ds.to_dict()).pip_count is None


# ── HandDet ───────────────────────────────────────────────────────────────────


def test_hand_det_roundtrip() -> None:
    h = HandDet(
        handedness="Left",
        wrist_xy=(0.4, 0.6),
        landmarks_21=[(float(i) * 0.01, float(i) * 0.02) for i in range(21)],
        gesture="ok_sign",
        player_id="p_xyz",
    )
    restored = HandDet.from_dict(h.to_dict())
    assert restored.handedness == h.handedness
    assert restored.wrist_xy == h.wrist_xy
    assert len(restored.landmarks_21) == 21
    assert restored.gesture == h.gesture
    assert restored.player_id == h.player_id


# ── FramePerception ───────────────────────────────────────────────────────────


def test_frame_perception_roundtrip() -> None:
    fp = _make_frame()
    restored = FramePerception.from_dict(fp.to_dict())
    assert restored.frame_id == fp.frame_id
    assert restored.ts == fp.ts
    assert restored.image_hw == fp.image_hw
    assert restored.roll_actor_id == fp.roll_actor_id
    assert len(restored.dice) == 1
    assert len(restored.hands) == 1
    assert restored.tray is not None
    assert restored.tray_inner is None
    assert restored.roll_tray is not None


def test_frame_perception_jsonl() -> None:
    fp = _make_frame()
    line = fp.to_jsonl_line()
    d = json.loads(line)
    restored = FramePerception.from_dict(d)
    assert restored.frame_id == fp.frame_id


def test_frame_perception_dice_all_stable_true() -> None:
    fp = _make_frame()  # dice stable_frames=31, stabilization=30
    assert fp.dice_all_stable(stabilization_frames=30) is True


def test_frame_perception_dice_all_stable_false() -> None:
    fp = _make_frame()
    fp.dice[0].stable_frames = 5
    assert fp.dice_all_stable(stabilization_frames=30) is False


def test_frame_perception_dice_all_stable_empty() -> None:
    fp = _make_frame()
    fp.dice = []
    assert fp.dice_all_stable(stabilization_frames=30) is False


def test_frame_perception_dice_values() -> None:
    fp = _make_frame()
    assert fp.dice_values() == [3]
