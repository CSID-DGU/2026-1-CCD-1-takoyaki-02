"""WerewolfVisionPipeline을 백그라운드 스레드로 실행하는 어댑터."""

from __future__ import annotations

import queue
import threading

from bridge.local_bridge import LocalBridge
from vision.werewolf.config import WerewolfVisionConfig
from vision.werewolf.pipeline import WerewolfVisionPipeline


class WerewolfRunner:
    def __init__(self, bridge: LocalBridge) -> None:
        self._bridge = bridge
        self._pipeline: WerewolfVisionPipeline | None = None
        self._thread: threading.Thread | None = None

    def start(self, frame_queue: "queue.Queue") -> None:
        config = WerewolfVisionConfig()
        self._pipeline = WerewolfVisionPipeline(
            config=config,
            bridge=self._bridge,
            players=[],
        )
        self._thread = threading.Thread(
            target=self._pipeline.start,
            args=(frame_queue,),
            daemon=True,
            name="werewolf-vision-pipeline",
        )
        self._thread.start()
        print("[werewolf_runner] 늑대인간 비전 파이프라인 시작")

    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()

    def set_active(self, enabled: bool) -> None:
        if self._pipeline is not None:
            self._pipeline.set_active(enabled)

    def update_players(self, players: list) -> None:
        if self._pipeline is not None:
            self._pipeline.update_players(players)
