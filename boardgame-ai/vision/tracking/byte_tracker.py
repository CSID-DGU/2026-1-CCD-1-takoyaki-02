"""경량 ByteTrack 스타일 다중 객체 트래커.

dice 전용. track_id를 롤 전·후에도 유지하는 것이 핵심.
Hungarian matching (lap 라이브러리) + IoU cost matrix.
"""

from __future__ import annotations

from dataclasses import dataclass

from vision.schemas import BBox, YoloDet

try:
    import lap  # type: ignore[import]

    _HAS_LAP = True
except ImportError:
    _HAS_LAP = False


def _iou_cost(a: BBox, b: BBox) -> float:
    """IoU 기반 cost (낮을수록 매칭 우선)."""
    return 1.0 - a.iou(b)


@dataclass
class _Track:
    track_id: int
    bbox: BBox
    age: int = 0  # 마지막 매칭 이후 프레임 수
    hit_streak: int = 1  # 연속 매칭 프레임 수


class ByteTracker:
    """
    Parameters
    ----------
    max_age         : 매칭 실패 허용 최대 프레임 수 (이 후 트랙 삭제)
    min_hits        : 트랙을 확정하기 위한 최소 연속 매칭 프레임
    iou_threshold   : IoU cost 임계값 (초과 시 매칭 거부)
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 2,
        iou_threshold: float = 0.5,
    ) -> None:
        self._max_age = max_age
        self._min_hits = min_hits
        self._iou_threshold = iou_threshold
        self._tracks: list[_Track] = []
        self._next_id = 1

    def update(self, dets: list[YoloDet], frame_id: int = 0) -> list[tuple[int, YoloDet]]:
        """
        Returns
        -------
        list of (track_id, YoloDet) — 확정된 트랙만 반환
        """
        if not self._tracks:
            for det in dets:
                self._tracks.append(_Track(track_id=self._next_id, bbox=det.bbox))
                self._next_id += 1
            return [
                (
                    t.track_id,
                    YoloDet(cls_name=det.cls_name, bbox=det.bbox, track_id=t.track_id),
                )
                for t, det in zip(self._tracks, dets, strict=False)
                if t.hit_streak >= self._min_hits
            ]

        matched, unmatched_dets, unmatched_trks = self._match(dets)

        # 매칭된 트랙 업데이트
        for det_idx, trk_idx in matched:
            self._tracks[trk_idx].bbox = dets[det_idx].bbox
            self._tracks[trk_idx].age = 0
            self._tracks[trk_idx].hit_streak += 1

        # 신규 감지 → 새 트랙
        for det_idx in unmatched_dets:
            self._tracks.append(_Track(track_id=self._next_id, bbox=dets[det_idx].bbox))
            self._next_id += 1

        # 매칭 실패 트랙 age 증가
        for trk_idx in unmatched_trks:
            self._tracks[trk_idx].age += 1
            self._tracks[trk_idx].hit_streak = 0

        # 오래된 트랙 제거
        self._tracks = [t for t in self._tracks if t.age <= self._max_age]

        # 확정 트랙 + 대응 det 반환
        results: list[tuple[int, YoloDet]] = []
        for det_idx, trk_idx in matched:
            trk = self._tracks[trk_idx] if trk_idx < len(self._tracks) else None
            if trk and trk.hit_streak >= self._min_hits:
                det = dets[det_idx]
                results.append(
                    (
                        trk.track_id,
                        YoloDet(cls_name=det.cls_name, bbox=det.bbox, track_id=trk.track_id),
                    )
                )

        return results

    def _match(self, dets: list[YoloDet]) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Hungarian matching. 반환: (matched, unmatched_dets, unmatched_trks)."""
        n_det = len(dets)
        n_trk = len(self._tracks)

        if n_det == 0:
            return [], [], list(range(n_trk))
        if n_trk == 0:
            return [], list(range(n_det)), []

        # cost matrix (n_det × n_trk)
        cost = [
            [_iou_cost(dets[i].bbox, self._tracks[j].bbox) for j in range(n_trk)]
            for i in range(n_det)
        ]

        if _HAS_LAP:
            matched, unmatched_dets, unmatched_trks = _hungarian_lap(
                cost, n_det, n_trk, self._iou_threshold
            )
        else:
            matched, unmatched_dets, unmatched_trks = _hungarian_greedy(
                cost, n_det, n_trk, self._iou_threshold
            )

        return matched, unmatched_dets, unmatched_trks


def _hungarian_lap(
    cost: list[list[float]],
    n_det: int,
    n_trk: int,
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    import numpy as np  # type: ignore[import]

    cost_np = np.array(cost, dtype=np.float64)
    _, x, _ = lap.lapjv(cost_np, extend_cost=True, cost_limit=threshold)

    matched = []
    unmatched_dets = []
    for det_idx, trk_idx in enumerate(x):
        if trk_idx >= 0 and cost[det_idx][trk_idx] <= threshold:
            matched.append((det_idx, int(trk_idx)))
        else:
            unmatched_dets.append(det_idx)

    matched_trks = {t for _, t in matched}
    unmatched_trks = [j for j in range(n_trk) if j not in matched_trks]
    return matched, unmatched_dets, unmatched_trks


def _hungarian_greedy(
    cost: list[list[float]],
    n_det: int,
    n_trk: int,
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """lap 없을 때 greedy fallback (O(n²))."""
    pairs: list[tuple[float, int, int]] = []
    for i in range(n_det):
        for j in range(n_trk):
            if cost[i][j] <= threshold:
                pairs.append((cost[i][j], i, j))
    pairs.sort()

    used_det: set[int] = set()
    used_trk: set[int] = set()
    matched: list[tuple[int, int]] = []
    for _, i, j in pairs:
        if i not in used_det and j not in used_trk:
            matched.append((i, j))
            used_det.add(i)
            used_trk.add(j)

    unmatched_dets = [i for i in range(n_det) if i not in used_det]
    unmatched_trks = [j for j in range(n_trk) if j not in used_trk]
    return matched, unmatched_dets, unmatched_trks
