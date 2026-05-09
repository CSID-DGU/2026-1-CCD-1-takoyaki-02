"""요트 다이스 비전 파이프라인 설정."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VisionConfig:
    # 카메라 / 소스 (CameraManager가 관리하므로 파이프라인에서 직접 사용하지 않음)
    source: int | str = 0
    resolution: tuple[int, int] = (1920, 1080)
    target_fps: int = 30
    frame_skip: int = 0

    # YOLO
    weights_path: str | Path = "weights/yacht_v4.pt"
    yolo_conf: float = 0.35
    yolo_iou: float = 0.5
    yolo_imgsz: int = 640

    # MediaPipe Hand
    mp_max_num_hands: int = 8
    mp_min_detection_confidence: float = 0.5
    mp_min_tracking_confidence: float = 0.5
    mp_model_complexity: int = 0

    # RollAttributor
    roll_lift_threshold: float = 0.02
    grab_fallback_window_frames: int = 60

    # DiceManager
    dice_count_buffer: int = 11
    dice_history_window: int = 10

    warmup_frames: int = 60
    tray_mask_padding: float = 0.1

    debug_overlay: bool = False
    jsonl_log_path: Path | None = None

    def __post_init__(self) -> None:
        self.weights_path = Path(self.weights_path)
        if self.jsonl_log_path is not None:
            self.jsonl_log_path = Path(self.jsonl_log_path)
