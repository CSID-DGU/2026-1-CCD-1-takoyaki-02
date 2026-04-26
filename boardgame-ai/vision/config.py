"""비전 파이프라인 하드웨어·IO 설정.

core/constants.DEFAULT_PARAMS 는 Fusion 파라미터(threshold, frames 수).
VisionConfig 는 카메라·모델·디버그 등 하드웨어·IO 파라미터.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VisionConfig:
    # 카메라 / 소스
    source: int | str = 0  # 카메라 인덱스 또는 mp4 경로
    resolution: tuple[int, int] = (1920, 1080)  # (width, height)
    target_fps: int = 30
    frame_skip: int = 0  # 0=모든 프레임, 1=격프레임, ...

    # YOLO
    weights_path: str | Path = "weights/yacht_best.pt"
    yolo_conf: float = 0.35
    yolo_iou: float = 0.5
    yolo_imgsz: int = 640  # 추론 해상도 (1080p 다운스케일)

    # MediaPipe
    mp_max_num_hands: int = 8
    mp_min_detection_confidence: float = 0.5
    mp_min_tracking_confidence: float = 0.5
    mp_model_complexity: int = 0  # 0=경량, 1=표준

    # RollAttributor
    roll_lift_threshold: float = 0.02  # roll_tray 들림 감지 (정규화 프레임간 이동)
    grab_fallback_window_frames: int = 60  # grab 실패 시 fallback K프레임

    # DiceManager
    dice_count_buffer: int = 11  # pip_count 다수결 버퍼 크기 (YOLO/Hough 끊김 흡수)
    dice_history_window: int = 10  # motion_score 계산용 이력 윈도우

    # 시작 시 카메라 자동노출/색온도 적응 흡수용 워밍업 프레임 수.
    # 이 동안은 GameEvent 송신을 skip (감지·overlay·로깅은 정상).
    warmup_frames: int = 60

    # tray 감지 시 dice center가 tray bbox + 패딩 밖이면 무시 (각도 흔들림 가짜 detection 차단).
    # 0.0~1.0, 0.1 = bbox 변 길이의 10% 패딩.
    tray_mask_padding: float = 0.1

    # 디버그·로깅
    debug_overlay: bool = False
    jsonl_log_path: Path | None = None

    def __post_init__(self) -> None:
        self.weights_path = Path(self.weights_path)
        if self.jsonl_log_path is not None:
            self.jsonl_log_path = Path(self.jsonl_log_path)
