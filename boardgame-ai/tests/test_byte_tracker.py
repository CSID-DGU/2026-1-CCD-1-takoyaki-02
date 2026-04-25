"""ByteTracker 단위 테스트 — track_id 안정성 / 가림·재매칭 회귀 방지.

특히 max_age 정리 시 인덱스 무효화 버그가 다시 들어오지 않는지 확인.
"""

from __future__ import annotations

from vision.schemas import BBox, YoloDet
from vision.tracking.byte_tracker import ByteTracker


def _det(x1: float, y1: float, x2: float, y2: float) -> YoloDet:
    return YoloDet(
        cls_name="dice",
        bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=0.9, cls_name="dice"),
    )


def test_track_id_persists_across_frames() -> None:
    tracker = ByteTracker(max_age=30, min_hits=2, iou_threshold=0.5)
    d = _det(0.1, 0.1, 0.2, 0.2)

    # 1프레임: 첫 등장, hit_streak=1 → 아직 미확정
    out1 = tracker.update([d], frame_id=0)
    assert out1 == []

    # 2프레임: 같은 위치 재등장 → 확정
    out2 = tracker.update([d], frame_id=1)
    assert len(out2) == 1
    tid_first = out2[0][0]

    # 3, 4프레임: 같은 track_id 유지
    out3 = tracker.update([d], frame_id=2)
    out4 = tracker.update([d], frame_id=3)
    assert out3[0][0] == tid_first
    assert out4[0][0] == tid_first


def test_track_id_persists_after_brief_occlusion() -> None:
    """가림으로 한두 프레임 사라져도 max_age 안에 재등장 시 같은 track_id로 회복."""
    tracker = ByteTracker(max_age=30, min_hits=2, iou_threshold=0.5)
    d = _det(0.4, 0.4, 0.5, 0.5)

    # 확정까지
    tracker.update([d], frame_id=0)
    out = tracker.update([d], frame_id=1)
    tid = out[0][0]

    # 2프레임 동안 detection 없음 (가림)
    tracker.update([], frame_id=2)
    tracker.update([], frame_id=3)

    # 재등장 — hit_streak 리셋 됐으므로 results는 한 프레임 뒤 채워짐
    tracker.update([d], frame_id=4)
    out_back = tracker.update([d], frame_id=5)
    assert len(out_back) == 1
    assert out_back[0][0] == tid


def test_old_tracks_dropped_after_max_age() -> None:
    """max_age를 넘기면 트랙은 사라지고, 동일 위치에 새 detection이 와도 새 ID 부여."""
    tracker = ByteTracker(max_age=2, min_hits=2, iou_threshold=0.5)
    d = _det(0.1, 0.1, 0.2, 0.2)

    tracker.update([d], frame_id=0)
    out = tracker.update([d], frame_id=1)
    tid_old = out[0][0]

    # 빈 detection 3프레임 (max_age=2 초과)
    tracker.update([], frame_id=2)
    tracker.update([], frame_id=3)
    tracker.update([], frame_id=4)

    # 다시 등장 — 새 track_id 부여돼야 함
    tracker.update([d], frame_id=5)
    out_new = tracker.update([d], frame_id=6)
    assert out_new[0][0] != tid_old


def test_track_id_unaffected_by_concurrent_track_removal() -> None:
    """매칭된 트랙이 살아있는데 다른 트랙이 max_age 초과로 제거되어도 매칭 결과의 track_id는 그대로.

    인덱스 무효화 버그 회귀 방지 — 트랙 리스트가 재구성되어도 results는 객체 레퍼런스 기준.
    """
    tracker = ByteTracker(max_age=2, min_hits=1, iou_threshold=0.5)
    d_left = _det(0.05, 0.5, 0.15, 0.6)
    d_right = _det(0.85, 0.5, 0.95, 0.6)

    # 두 주사위 등장
    out0 = tracker.update([d_left, d_right], frame_id=0)
    ids = sorted(t[0] for t in out0)
    tid_left, tid_right = ids[0], ids[1]

    # left 사라지고 right만 남음 (max_age 초과까지)
    tracker.update([d_right], frame_id=1)
    tracker.update([d_right], frame_id=2)
    out3 = tracker.update([d_right], frame_id=3)

    # left가 정리되는 프레임에서도 right의 track_id는 일관되게 유지
    assert len(out3) == 1
    # tid_right은 처음 두 트랙 중 하나 — 어떤 게 right였든 일관성만 검증
    assert out3[0][0] in (tid_left, tid_right)
    # 그리고 다음 프레임에서도 같은 ID
    out4 = tracker.update([d_right], frame_id=4)
    assert out4[0][0] == out3[0][0]


def test_new_detection_assigns_new_id() -> None:
    tracker = ByteTracker(max_age=10, min_hits=1, iou_threshold=0.5)
    d1 = _det(0.1, 0.1, 0.2, 0.2)
    d2 = _det(0.7, 0.7, 0.8, 0.8)  # 멀리 떨어진 새 객체

    out0 = tracker.update([d1], frame_id=0)
    tid1 = out0[0][0]

    # d2 첫 등장 시점에는 unmatched_dets로 들어가 신규 트랙만 만들고 results에 안 들어감
    tracker.update([d1, d2], frame_id=1)
    # 다음 프레임에서 재매칭되어 d2도 results에 포함됨
    out2 = tracker.update([d1, d2], frame_id=2)
    ids = {t[0] for t in out2}
    assert tid1 in ids
    assert len(ids) == 2
