"""한밤의 늑대인간 카드 YOLO 감지기.

model_path 에 지정한 .pt 파일이 존재하면 YOLO 모델을 로드하고,
없으면 graceful fallback — detect() 가 항상 빈 리스트를 반환한다.

YOLO 학습 완료 후:
  1. best.pt 를 vision/weights/werewolf_cards.pt 로 복사
  2. 코드 변경 없음 — WerewolfCardDetector 가 자동으로 모델 로드

YOLO 학습 클래스:
  역할(앞면): werewolf, seer, robber, troublemaker, drunk,
              insomniac, villager, hunter, tanner
  뒷면: card_back
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vision.schemas import BBox
from vision.werewolf.schemas import ALL_CARD_CLASSES, CardDetRaw

# YOLO 학습 완료 후 이 경로에 .pt 파일을 놓으면 자동 활성화
_DEFAULT_MODEL_PATH = "vision/weights/werewolf_cards.pt"


class WerewolfCardDetector:
    """YOLO 기반 늑대인간 카드 감지기.

    Parameters
    ----------
    model_path : str | Path
        학습된 .pt 파일 경로. 파일이 없으면 항상 빈 리스트 반환.
    conf : float
        YOLO confidence threshold
    iou : float
        YOLO NMS IoU threshold
    imgsz : int
        YOLO 추론 해상도 (단변 길이)
    """

    def __init__(
        self,
        model_path: str | Path = _DEFAULT_MODEL_PATH,
        conf: float = 0.50,
        iou: float = 0.45,
        imgsz: int = 640,
    ) -> None:
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        self._model: Any = None
        self._cls_names: dict[int, str] = {}

        model_path = Path(model_path)
        if model_path.exists():
            try:
                from ultralytics import YOLO  # type: ignore[import]

                self._model = YOLO(str(model_path))
                self._cls_names = {
                    int(k): str(v) for k, v in self._model.names.items()
                }
                print(f"[card_detector] YOLO 모델 로드 완료: {model_path}")
            except Exception as exc:
                print(f"[card_detector] YOLO 모델 로드 실패: {exc}  → fallback 모드")
                self._model = None
        else:
            print(
                f"[card_detector] 모델 파일 없음: {model_path}  → fallback 모드 "
                f"(학습 완료 후 해당 경로에 .pt 파일 추가)"
            )

    @property
    def is_loaded(self) -> bool:
        """모델이 정상적으로 로드됐는지 여부."""
        return self._model is not None

    def detect(self, frame_bgr: Any) -> list[CardDetRaw]:
        """BGR 프레임 → CardDetRaw 리스트. 모델 없으면 빈 리스트."""
        if self._model is None:
            return []

        results = self._model(
            frame_bgr,
            conf=self._conf,
            iou=self._iou,
            imgsz=self._imgsz,
            verbose=False,
        )
        result = results[0]
        h, w = result.orig_shape

        dets: list[CardDetRaw] = []
        for box in result.boxes:
            cls_name = self._cls_names.get(int(box.cls[0]), "")
            if cls_name not in ALL_CARD_CLASSES:
                continue
            conf_val = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            bbox = BBox(
                x1=xyxy[0] / w,
                y1=xyxy[1] / h,
                x2=xyxy[2] / w,
                y2=xyxy[3] / h,
                conf=conf_val,
                cls_name=cls_name,
            )
            dets.append(CardDetRaw(bbox=bbox, cls_name=cls_name, conf=conf_val))

        return dets
