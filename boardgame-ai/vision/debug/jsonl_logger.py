"""JSONL 프레임 로거.

config.jsonl_log_path 가 None 이면 no-op.
오프라인 재현·튜닝·회귀 테스트용.
"""

from __future__ import annotations

import io
from pathlib import Path

from vision.schemas import FramePerception


class JsonlLogger:
    def __init__(self, path: Path | None) -> None:
        self._file: io.TextIOWrapper | None = None
        if path is not None:
            self._file = path.open("a", encoding="utf-8")

    def log(self, perception: FramePerception) -> None:
        if self._file is None:
            return
        self._file.write(perception.to_jsonl_line() + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __del__(self) -> None:
        self.close()
