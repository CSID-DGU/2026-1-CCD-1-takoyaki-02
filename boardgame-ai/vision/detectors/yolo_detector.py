"""YOLO 기반 요트다이스 객체 감지.

감지 클래스: tray / tray_inner / roll_tray / dice
- tray / tray_inner / roll_tray: 프레임당 최대 1개 (최고 신뢰도)
- dice: n개 (모두 반환)
좌표는 정규화 float64 (0.0~1.0).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vision.schemas import BBox, YoloDet

_SINGLETON_CLASSES = {"tray", "tray_inner", "roll_tray"}
_VALID_CLASSES = {"tray", "tray_inner", "roll_tray", "dice"}


class YoloDetector:
    def __init__(
        self,
        weights_path: str | Path,
        conf: float = 0.35,
        iou: float = 0.5,
        imgsz: int = 640,
    ) -> None:
        from ultralytics import YOLO  # type: ignore[import]

        self._model = YOLO(str(weights_path))
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        # 클래스 이름 → index 역매핑 (모델에 없는 클래스 감지 방지)
        self._cls_names: dict[int, str] = {
            int(k): str(v) for k, v in self._model.names.items()
        }

    def detect(self, frame_bgr: Any) -> list[YoloDet]:
        """BGR 프레임 → YoloDet 리스트. 정규화 좌표."""
        results = self._model(
            frame_bgr,
            conf=self._conf,
            iou=self._iou,
            imgsz=self._imgsz,
            verbose=False,
        )
        result = results[0]

        h, w = result.orig_shape  # 원본 해상도
        boxes = result.boxes

        raw: dict[str, list[YoloDet]] = {c: [] for c in _VALID_CLASSES}

        for box in boxes:
            cls_idx = int(box.cls[0])
            cls_name = self._cls_names.get(cls_idx, "")
            if cls_name not in _VALID_CLASSES:
                continue

            conf_val = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2] 픽셀
            bbox = BBox(
                x1=xyxy[0] / w,
                y1=xyxy[1] / h,
                x2=xyxy[2] / w,
                y2=xyxy[3] / h,
                conf=conf_val,
                cls_name=cls_name,
            )
            raw[cls_name].append(YoloDet(cls_name=cls_name, bbox=bbox))

        dets: list[YoloDet] = []

        # 단일 클래스: 최고 신뢰도 1개만
        for cls_name in _SINGLETON_CLASSES:
            candidates = raw[cls_name]
            if candidates:
                best = max(candidates, key=lambda d: d.bbox.conf)
                dets.append(best)

        # dice: 전부 추가
        dets.extend(raw["dice"])

        return dets
