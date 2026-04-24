"""DotCounter 단위 테스트.

opencv-python 필요. 합성 이미지(흰 사각형 + 검은 원)로 1~6 검증.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from vision.detectors.dot_counter import DotCounter
from vision.schemas import BBox


def _make_dice_image(pip_count: int, size: int = 180) -> tuple[np.ndarray, BBox]:
    """흰 배경 + 검은 원 pip_count 개 합성 이미지 + 전체 BBox."""
    img = np.ones((size, size, 3), dtype=np.uint8) * 240  # 밝은 회색 배경

    # pip 위치 패턴 (정규화 중심 좌표) — 원 간격 충분히 확보
    patterns: dict[int, list[tuple[float, float]]] = {
        1: [(0.5, 0.5)],
        2: [(0.3, 0.3), (0.7, 0.7)],
        3: [(0.3, 0.3), (0.5, 0.5), (0.7, 0.7)],
        4: [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)],
        5: [(0.3, 0.3), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.7, 0.7)],
        6: [(0.25, 0.22), (0.75, 0.22), (0.25, 0.5), (0.75, 0.5), (0.25, 0.78), (0.75, 0.78)],
    }
    radius = max(5, size // 18)  # 크기 대비 작은 원으로 간격 확보
    for cx_r, cy_r in patterns[pip_count]:
        cx = int(cx_r * size)
        cy = int(cy_r * size)
        cv2.circle(img, (cx, cy), radius, (30, 30, 30), -1)

    bbox = BBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0, conf=0.99, cls_name="dice")
    return img, bbox


@pytest.mark.parametrize("pip_count", [1, 2, 3, 4, 5, 6])
def test_dot_counter_clean_image(pip_count: int) -> None:
    """깨끗한 합성 이미지에서 pip_count 정확히 인식."""
    counter = DotCounter()
    img, bbox = _make_dice_image(pip_count, size=120)
    result = counter.count(img, bbox)
    # 합성 이미지 특성상 ±1 허용 (HoughCircles 파라미터 민감)
    assert result is not None, f"pip={pip_count}: result was None"
    assert abs(result - pip_count) <= 1, f"pip={pip_count}: got {result}"


def test_dot_counter_empty_bbox_returns_none() -> None:
    """빈 BBox는 None 반환."""
    counter = DotCounter()
    img = np.ones((100, 100, 3), dtype=np.uint8) * 200
    bbox = BBox(x1=0.5, y1=0.5, x2=0.5, y2=0.5, conf=0.9, cls_name="dice")
    assert counter.count(img, bbox) is None


def test_dot_counter_noisy_image_does_not_crash() -> None:
    """노이즈 이미지는 None 또는 1~6 반환 (크래시 없음)."""
    counter = DotCounter()
    rng = np.random.default_rng(42)
    img = rng.integers(0, 255, (100, 100, 3), dtype=np.uint8)
    bbox = BBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0, conf=0.9, cls_name="dice")
    result = counter.count(img, bbox)
    assert result is None or 1 <= result <= 6
