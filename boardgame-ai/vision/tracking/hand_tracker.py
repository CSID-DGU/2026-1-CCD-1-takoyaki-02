"""손 위치 기반 프레임 간 HandTrack 유지.

MediaPipe HandLandmarker는 프레임마다 손 인덱스가 재배정되고
가림·빠른 움직임에 track이 끊기기 쉬움. 이를 보완하기 위해:
  - wrist 좌표 근접도(Euclidean) 기반 greedy 1:1 매칭으로
    frame-to-frame 트랙 유지 (최대 4명 손이라 greedy로 충분)
  - handedness/player_id는 deque 버퍼 다수결로 안정화
  - 신규 track 발생 시 entry_wrist_xy + entry_arm_angle 영구 저장
  - pending_match=True → pipeline이 매칭 1회 수행

byte_tracker.py의 구조를 참고했으나 IoU 대신 wrist Euclidean distance 사용.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass, field

# 한 프레임 사이 wrist가 이동할 수 있는 최대 정규화 거리.
# 초과 시 다른 사람 손으로 판정.
_MAX_WRIST_DIST = 0.15

# handedness / player_id 다수결 버퍼 크기.
_HANDEDNESS_BUF = 7
_PLAYER_ID_BUF = 7

# 이 프레임 수 이상 매칭 안 되면 track 제거.
_MAX_AGE = 15


@dataclass
class HandTrack:
    """프레임 간 한 손의 연속 추적 상태."""

    track_id: int
    wrist_xy: tuple[float, float]
    arm_angle: float  # 매 프레임 갱신되는 현재 각도

    # 트랙 시작 시점 정보 (영구) — 매칭에 사용
    entry_wrist_xy: tuple[float, float] = (0.0, 0.0)
    entry_arm_angle: float = 0.0

    # 다수결 버퍼
    handedness_buf: deque[str] = field(default_factory=lambda: deque(maxlen=_HANDEDNESS_BUF))
    player_id_buf: deque[str | None] = field(default_factory=lambda: deque(maxlen=_PLAYER_ID_BUF))

    age: int = 0  # 마지막 매칭 이후 프레임 수
    frames_since_entry: int = 0  # 트랙 생성 이후 매칭된 프레임 수
    pending_match: bool = True  # 신규 track → 매칭 1회 대기

    @property
    def confirmed_handedness(self) -> str | None:
        if not self.handedness_buf:
            return None
        return Counter(self.handedness_buf).most_common(1)[0][0]

    @property
    def confirmed_player_id(self) -> str | None:
        if not self.player_id_buf:
            return None
        counts = Counter(p for p in self.player_id_buf if p is not None)
        if not counts:
            return None
        return counts.most_common(1)[0][0]


class HandTracker:
    """wrist 좌표 기반 프레임 간 손 추적기.

    Parameters
    ----------
    max_wrist_dist : 매칭 허용 최대 wrist 거리 (정규화)
    max_age        : track 유지 최대 미매칭 프레임 수
    """

    def __init__(
        self,
        max_wrist_dist: float = _MAX_WRIST_DIST,
        max_age: int = _MAX_AGE,
    ) -> None:
        self._max_dist = max_wrist_dist
        self._max_age = max_age
        self._tracks: list[HandTrack] = []
        self._next_id = 1

    def update(
        self,
        detections: list[tuple[tuple[float, float], float]],
    ) -> list[HandTrack]:
        """감지된 손의 (wrist, arm_angle) 리스트로 track을 갱신하고 활성 track 반환.

        Parameters
        ----------
        detections : 이번 프레임에서 감지된 손들의 (wrist_xy, arm_angle) 리스트

        Returns
        -------
        이번 프레임에 매칭된 HandTrack 리스트 (입력 순서 대응).
        매칭 안 된 손 → 신규 track 생성 (entry_* 저장, pending_match=True).
        """
        wrist_positions = [d[0] for d in detections]
        arm_angles = [d[1] for d in detections]
        n_det = len(detections)
        n_trk = len(self._tracks)

        matched_tracks: list[HandTrack | None] = [None] * n_det

        if n_trk > 0 and n_det > 0:
            cost = [
                [_euclidean(wrist_positions[i], self._tracks[j].wrist_xy) for j in range(n_trk)]
                for i in range(n_det)
            ]
            matched_pairs, unmatched_dets, unmatched_trks = _greedy_match(
                cost, n_det, n_trk, self._max_dist
            )
        else:
            matched_pairs = []
            unmatched_dets = list(range(n_det))
            unmatched_trks = list(range(n_trk))

        # 매칭된 track 갱신
        for det_idx, trk_idx in matched_pairs:
            trk = self._tracks[trk_idx]
            trk.wrist_xy = wrist_positions[det_idx]
            trk.arm_angle = arm_angles[det_idx]
            trk.age = 0
            trk.frames_since_entry += 1
            matched_tracks[det_idx] = trk

        # 매칭 실패 track age 증가
        for trk_idx in unmatched_trks:
            self._tracks[trk_idx].age += 1

        # 신규 track 생성 — entry 정보 영구 저장
        for det_idx in unmatched_dets:
            wxy = wrist_positions[det_idx]
            ang = arm_angles[det_idx]
            new_trk = HandTrack(
                track_id=self._next_id,
                wrist_xy=wxy,
                arm_angle=ang,
                entry_wrist_xy=wxy,
                entry_arm_angle=ang,
                pending_match=True,
            )
            self._next_id += 1
            self._tracks.append(new_trk)
            matched_tracks[det_idx] = new_trk

        # 오래된 track 제거
        self._tracks = [t for t in self._tracks if t.age <= self._max_age]

        return [t for t in matched_tracks if t is not None]

    def get_track_by_id(self, track_id: int) -> HandTrack | None:
        for t in self._tracks:
            if t.track_id == track_id:
                return t
        return None

    def active_tracks(self) -> list[HandTrack]:
        """현재 살아있는 모든 track (age <= max_age)."""
        return list(self._tracks)


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _greedy_match(
    cost: list[list[float]],
    n_det: int,
    n_trk: int,
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy 1:1 매칭. lap 의존 없이 동작."""
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
