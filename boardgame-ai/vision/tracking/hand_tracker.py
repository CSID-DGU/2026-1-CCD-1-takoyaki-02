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

# Hold 모드 최대 매칭 시도 프레임 수. 옆자리 후보와 margin이 부족해
# 모호한 동안 voting 누적, 이 횟수 도달 시 best로 강제 confirm(타임아웃).
MAX_MATCH_ATTEMPTS = 5


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
    pending_match: bool = True  # Hold 모드: 매칭 시도 반복 중. 확정 시 False.
    match_attempts: int = 0  # Hold 중 누적 매칭 시도 수 (타임아웃 카운터)
    # 마지막 player_id 매칭에 사용된 handedness — handedness 다수결이 뒤집히면
    # 재매칭이 필요하므로 비교 키로 사용. None이면 아직 한 번도 매칭 시도 안 함.
    last_match_handedness: str | None = None

    @property
    def confirmed_handedness(self) -> str | None:
        """다수결 + 최소 표수 + 우세 마진 검증.

        초반 1~2프레임만으로 confirmed가 결정되면 MediaPipe의 초기 오인식이
        그대로 굳어 잘못된 player_id 매칭을 유발한다. 최소 3표 + 2위 대비
        2표 이상 우세여야 confirmed 반환. 미달이면 None (= 매칭 보류 신호).
        """
        if len(self.handedness_buf) < 3:
            return None
        top = Counter(self.handedness_buf).most_common(2)
        if not top:
            return None
        candidate, votes = top[0]
        runner_up = top[1][1] if len(top) > 1 else 0
        if votes < 3 or (votes - runner_up) < 2:
            return None
        return candidate

    @property
    def confirmed_player_id(self) -> str | None:
        """player_id 다수결. None 표는 무시하고 실제 매칭된 값들의 최빈값.

        Hold 모드 + 강제 confirm 이후에도 player_id_buf를 계속 누적해
        시간 다수결로 초기 오매칭을 자정한다.
        """
        if not self.player_id_buf:
            return None
        counts = Counter(p for p in self.player_id_buf if p is not None)
        if not counts:
            return None
        top = counts.most_common(2)
        candidate, votes = top[0]
        runner_up = top[1][1] if len(top) > 1 else 0
        # 단발 표는 임시 매칭일 수 있으므로 2표 이상 또는 1위/2위 명확할 때만 confirm.
        if votes < 2 or (votes - runner_up) < 1:
            return None
        return candidate

    @property
    def best_effort_player_id(self) -> str | None:
        """마진 검증 없이 player_id_buf의 최빈 non-None 값.

        confirmed_player_id는 초기 오매칭 굳음을 막으려 "2표+마진" 게이트를 걸어
        매칭이 잡혔어도 None을 돌려줄 수 있다. 그러나 옆사람이 잠깐 손을 뻗어
        굴린 짧은 트랙은 그 게이트를 통과할 표를 못 모아 player_id가 None이 되고,
        그러면 actor 산정이 None → 굴림이 현재 플레이어로 오인되어 차례 경고가
        누락된다. 한 번이라도 매칭된 적 있으면(=등록된 손 중 가장 가까운 후보가
        잡혔으면) None 대신 그 최빈값을 돌려, "등록된 손은 항상 누군가로 매칭"이라는
        원래 설계를 actor 경로에서 보장한다."""
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
