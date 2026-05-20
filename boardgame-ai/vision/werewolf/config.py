"""WerewolfVisionPipeline 설정."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WerewolfVisionConfig:
    """WerewolfVisionPipeline 하드웨어·IO 설정."""

    # 카메라 / 소스
    source: int | str = 0
    resolution: tuple[int, int] = (1920, 1080)
    target_fps: int = 30
    frame_skip: int = 2

    # YOLO 카드 감지 모델
    # 학습 완료 후 이 경로에 .pt 파일을 두면 자동 로드
    card_weights_path: str | Path = "weights/werewolf_cards.pt"
    yolo_conf: float = 0.50
    yolo_iou: float = 0.45
    yolo_imgsz: int = 640

    # MediaPipe Hand
    mp_max_num_hands: int = 8
    mp_min_detection_confidence: float = 0.5
    mp_min_tracking_confidence: float = 0.5

    # 카드-플레이어 근접 매칭 임계 (정규화 거리)
    card_player_match_threshold: float = 0.25

    # 시작 시 워밍업 프레임 (이 기간은 GameEvent 송신 skip)
    warmup_frames: int = 60

    # 디버그·로깅
    debug_overlay: bool = False
    jsonl_log_path: Path | None = None

    def __post_init__(self) -> None:
        self.card_weights_path = Path(self.card_weights_path)
        if self.jsonl_log_path is not None:
            self.jsonl_log_path = Path(self.jsonl_log_path)
