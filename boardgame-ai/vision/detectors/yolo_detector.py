"""YOLO 기반 요트다이스 객체 감지.

감지 클래스: tray / tray_inner / roll_tray / dice
- tray / tray_inner / roll_tray: 프레임당 최대 1개 (최고 신뢰도)
- dice: 최대 5개. 가짜·중복 detection 방지 위해 클래스 내 NMS 후 conf 내림차순 컷.
좌표는 정규화 float64 (0.0~1.0).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vision.schemas import BBox, YoloDet

_VALID_CLASSES = {"tray", "tray_inner", "roll_tray", "dice"}
# 클래스별 프레임당 허용 최대 개수 (요트다이스 게임 사양)
_MAX_PER_CLASS: dict[str, int] = {
    "tray": 1,
    "tray_inner": 1,
    "roll_tray": 1,
    "dice": 5,
}
# 같은 dice 박스 중복 판정 — 두 dice 중심거리가 작은 박스 변 길이의 이 비율보다
# 가까우면 conf 낮은 쪽을 제거 (NMS가 못 잡는 살짝 겹치는 케이스 차단)
_DICE_DEDUP_RATIO: float = 0.5


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
        self._cls_names: dict[int, str] = {int(k): str(v) for k, v in self._model.names.items()}

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

        # tray/tray_inner/roll_tray: 최고 신뢰도 1개만
        for cls_name in ("tray", "tray_inner", "roll_tray"):
            candidates = raw[cls_name]
            if candidates:
                best = max(candidates, key=lambda d: d.bbox.conf)
                dets.append(best)

        # dice: 중심거리 dedupe → conf 내림차순으로 max_count 컷
        dice_list = sorted(raw["dice"], key=lambda d: d.bbox.conf, reverse=True)
        dice_list = _dedupe_dice(dice_list)
        dets.extend(dice_list[: _MAX_PER_CLASS["dice"]])

        return dets


def _dedupe_dice(dice_sorted: list[YoloDet]) -> list[YoloDet]:
    """conf 내림차순으로 들어온 dice 리스트에서 중심거리 가까운 중복 제거.

    NMS 후에도 살짝 겹쳐 남는 이중 박스를 차단. 더 높은 conf를 우선 유지.
    """
    kept: list[YoloDet] = []
    for cand in dice_sorted:
        cx, cy = cand.bbox.center()
        size_c = min(cand.bbox.w, cand.bbox.h)
        is_dup = False
        for k in kept:
            kx, ky = k.bbox.center()
            size_k = min(k.bbox.w, k.bbox.h)
            min_size = min(size_c, size_k)
            if min_size <= 0:
                continue
            dist = ((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5
            if dist < min_size * _DICE_DEDUP_RATIO:
                is_dup = True
                break
        if not is_dup:
            kept.append(cand)
    return kept
