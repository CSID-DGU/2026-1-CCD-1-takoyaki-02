"""단일 카메라 관리자.

카메라를 한 번만 열고 여러 파이프라인에 프레임을 배분한다.
각 파이프라인은 subscribe()로 queue.Queue를 받아 독립적으로 소비한다.
큐가 꽉 차면 오래된 프레임을 버리고 최신 프레임을 넣는다 (drop-oldest).
"""

from __future__ import annotations

import queue
import threading
from typing import Any

import cv2


class CameraManager:
    def __init__(
        self,
        source: int | str = 0,
        resolution: tuple[int, int] = (1920, 1080),
        fps: int = 30,
    ) -> None:
        self._source = source
        self._resolution = resolution
        self._fps = fps
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def subscribe(self, maxsize: int = 2) -> queue.Queue:
        """프레임 큐 생성 후 반환. 파이프라인은 이 큐에서 프레임을 소비한다."""
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.append(q)
        return q

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="camera-manager"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        cap = cv2.VideoCapture(self._source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        cap.set(cv2.CAP_PROP_FPS, self._fps)

        print(
            f"[camera] opened={cap.isOpened()}  "
            f"w={cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}  "
            f"h={cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f}  "
            f"fps={cap.get(cv2.CAP_PROP_FPS):.0f}"
        )

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    print("[camera] cap.read() False — 카메라 연결 끊김")
                    break
                with self._lock:
                    qs = list(self._queues)
                for q in qs:
                    if q.full():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                    try:
                        q.put_nowait(frame)
                    except queue.Full:
                        pass
        finally:
            cap.release()
