"""주사위 트래킹 이력 관리 및 DiceState 조립.

ByteTracker가 track_id를 유지하고,
DiceManager는 track_id별 motion_score / stable_frames / pip_count를 관리.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

from vision.detectors.dot_counter import DotCounter
from vision.schemas import DiceState, YoloDet


@dataclass
class _DiceHistory:
    """track_id별 이력."""

    center_history: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=10))
    pip_buffer: deque[int] = field(default_factory=lambda: deque(maxlen=5))
    stable_frames: int = 0
    last_pip: int | None = None
    miss_count: int = 0  # tracked에서 빠진 연속 프레임 수 (가림 시 history 보존용)


class DiceManager:
    """
    Parameters
    ----------
    motion_threshold : 주사위 정지 판정 기준 (정규화 center 이동 표준편차)
    stabilization_frames : stable로 확정하기 위한 최소 프레임 수
    history_window : motion_score 계산용 이력 윈도우 크기
    pip_buffer_size : pip_count 다수결 버퍼 크기
    history_max_miss : tracked에서 사라진 후 history를 유지할 최대 프레임 수
                       (ByteTracker.max_age와 동일 정책 — 일시 가림 후 재매칭 시 pip 유지)
    """

    def __init__(
        self,
        motion_threshold: float = 0.002,
        stabilization_frames: int = 15,
        history_window: int = 10,
        pip_buffer_size: int = 7,
        history_max_miss: int = 30,
    ) -> None:
        self._motion_threshold = motion_threshold
        self._stabilization_frames = stabilization_frames
        self._history_window = history_window
        self._pip_buffer_size = pip_buffer_size
        self._history_max_miss = history_max_miss
        self._histories: dict[int, _DiceHistory] = {}

    def update(
        self,
        tracked: list[tuple[int, YoloDet]],
        frame_bgr: Any,
        dot_counter: DotCounter,
    ) -> list[DiceState]:
        """
        Parameters
        ----------
        tracked   : ByteTracker.update() 결과 [(track_id, YoloDet), ...]
        frame_bgr : 원본 BGR 프레임 (DotCounter 호출용)
        dot_counter : DotCounter 인스턴스

        Returns
        -------
        list[DiceState] — 현재 프레임의 모든 추적 주사위 상태
        """
        active_ids = {tid for tid, _ in tracked}

        # tracked에 없는 history는 즉시 지우지 않고 miss_count 누적.
        # 손에 가려졌다가 같은 track_id로 돌아올 수 있으므로 max_miss 동안 유지.
        for tid, hist in list(self._histories.items()):
            if tid not in active_ids:
                hist.miss_count += 1
                if hist.miss_count > self._history_max_miss:
                    del self._histories[tid]

        states: list[DiceState] = []

        for track_id, det in tracked:
            hist = self._histories.setdefault(
                track_id,
                _DiceHistory(
                    center_history=deque(maxlen=self._history_window),
                    pip_buffer=deque(maxlen=self._pip_buffer_size),
                ),
            )

            hist.miss_count = 0  # 다시 잡힘 — 가림 카운터 리셋

            center = det.bbox.center()
            hist.center_history.append(center)

            motion_score = _compute_motion_score(hist.center_history)
            is_stable = motion_score < self._motion_threshold

            if is_stable:
                hist.stable_frames += 1
            else:
                hist.stable_frames = 0

            # stable 확정 구간에서만 pip_count 갱신
            if hist.stable_frames >= self._stabilization_frames:
                pip = dot_counter.count(frame_bgr, det.bbox)
                if pip is not None:
                    hist.pip_buffer.append(pip)
                    # 과반 이상 동일 값이어야 last_pip 갱신 (소수 오인식 무시)
                    candidate = _majority_vote(hist.pip_buffer)
                    if candidate is not None:
                        buf_list = list(hist.pip_buffer)
                        if buf_list.count(candidate) > len(buf_list) // 2:
                            hist.last_pip = candidate
            else:
                # 흔들리는 프레임 → 직전 stable 값 유지
                pass

            states.append(
                DiceState(
                    track_id=track_id,
                    bbox=det.bbox,
                    center=center,
                    motion_score=motion_score,
                    stable_frames=hist.stable_frames,
                    pip_count=hist.last_pip,
                )
            )

        return states

    def reset(self) -> None:
        self._histories.clear()


def _compute_motion_score(history: deque[tuple[float, float]]) -> float:
    """최근 N프레임 center 이동의 표준편차 (정규화).

    샘플이 부족하면 큰 값을 반환해 가짜 stable 판정을 막는다.
    (variance 계산상 작은 표본은 0에 가까워 motion_threshold 미만으로 떨어짐)
    """
    if len(history) < 5:
        return float("inf")
    dists: list[float] = []
    pts = list(history)
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        dists.append((dx * dx + dy * dy) ** 0.5)
    mean = sum(dists) / len(dists)
    variance = sum((d - mean) ** 2 for d in dists) / len(dists)
    return variance**0.5


def _majority_vote(buf: deque[int]) -> int | None:
    if not buf:
        return None
    most_common = Counter(buf).most_common(1)
    return most_common[0][0] if most_common else None
