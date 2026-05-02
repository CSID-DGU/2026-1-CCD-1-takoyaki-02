"""VisionPipeline을 백그라운드 스레드로 실행하는 어댑터."""

from __future__ import annotations

import threading
from pathlib import Path

from bridge.local_bridge import LocalBridge
from vision.config import VisionConfig
from vision.pipeline import VisionPipeline


class VisionRunner:
    def __init__(self, config: VisionConfig, bridge: LocalBridge) -> None:
        self._config = config
        self._bridge = bridge
        self._pipeline: VisionPipeline | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        weights = Path(self._config.weights_path)
        if not weights.exists():
            print(
                f"[vision_runner] 가중치 파일 없음: {weights} — 비전 파이프라인 없이 백엔드만 시작합니다."
            )
            return

        self._pipeline = VisionPipeline(
            config=self._config,
            bridge=self._bridge,
            players=[],
        )
        self._thread = threading.Thread(
            target=self._pipeline.start,
            daemon=True,
            name="vision-pipeline",
        )
        self._thread.start()
        print(f"[vision_runner] 비전 파이프라인 시작 (weights={weights})")

    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()

    def update_players(self, players: list) -> None:
        if self._pipeline is not None:
            self._pipeline.update_players(players)
