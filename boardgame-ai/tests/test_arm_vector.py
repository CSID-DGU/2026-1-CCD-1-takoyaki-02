"""arm_vector 유틸 단위 테스트."""

import math

import pytest

from vision.geometry.arm_vector import (
    angular_diff,
    compute_arm_angle,
    estimate_body_xy,
    extrapolate_body_from_hand,
)


def _make_landmarks(wrist, mcp):
    """21개 landmark 중 wrist(0)와 middle_mcp(9)만 의미 있게 채운다."""
    lms = [(0.0, 0.0)] * 21
    lms[0] = wrist
    lms[9] = mcp
    return lms


# ── compute_arm_angle ────────────────────────────────────────────────────────


def test_compute_arm_angle_bottom():
    """손이 아래에서 들어옴: wrist가 mcp보다 아래(y 큼) → +π/2."""
    lms = _make_landmarks((0.5, 0.7), (0.5, 0.5))
    assert compute_arm_angle(lms) == pytest.approx(math.pi / 2, abs=1e-6)


def test_compute_arm_angle_top():
    """손이 위에서 들어옴: wrist가 mcp보다 위(y 작음) → -π/2."""
    lms = _make_landmarks((0.5, 0.3), (0.5, 0.5))
    assert compute_arm_angle(lms) == pytest.approx(-math.pi / 2, abs=1e-6)


def test_compute_arm_angle_left():
    """손이 왼쪽에서 들어옴: wrist가 mcp보다 왼쪽 → π."""
    lms = _make_landmarks((0.3, 0.5), (0.5, 0.5))
    assert compute_arm_angle(lms) == pytest.approx(math.pi, abs=1e-6)


def test_compute_arm_angle_right():
    """손이 오른쪽에서 들어옴: wrist가 mcp보다 오른쪽 → 0."""
    lms = _make_landmarks((0.7, 0.5), (0.5, 0.5))
    assert compute_arm_angle(lms) == pytest.approx(0.0, abs=1e-6)


def test_compute_arm_angle_short_landmarks():
    """21개 미만이면 0.0 반환."""
    assert compute_arm_angle([(0.0, 0.0)]) == 0.0


# ── angular_diff ─────────────────────────────────────────────────────────────


def test_angular_diff_basic():
    assert angular_diff(0.0, 1.0) == pytest.approx(1.0)
    assert angular_diff(1.0, 0.0) == pytest.approx(1.0)


def test_angular_diff_wraparound():
    """3.0 vs -3.0 → 둘 다 ±π 근처 → 작은 차이."""
    d = angular_diff(3.0, -3.0)
    assert d < 0.5


def test_angular_diff_opposite():
    """완전 반대(π 차이) → π."""
    assert angular_diff(0.0, math.pi) == pytest.approx(math.pi)


# ── estimate_body_xy ─────────────────────────────────────────────────────────


def test_estimate_body_xy_stretched():
    """양팔 일직선 (right=0, left=π) → stretched, body는 중앙에서 외삽."""
    body, posture = estimate_body_xy((0.7, 0.5), 0.0, (0.3, 0.5), math.pi)
    assert posture == "stretched"
    # mid_wrist=(0.5, 0.5), 평균 각도는 의미 있는 방향 — 좌석은 화면 외곽
    assert body[0] == pytest.approx(0.5, abs=0.5)


def test_estimate_body_xy_bent():
    """양팔 V자 꺾임 (둘 다 비슷한 방향) → bent."""
    body, posture = estimate_body_xy((0.6, 0.5), math.pi / 2 + 0.3, (0.4, 0.5), math.pi / 2 - 0.3)
    assert posture == "bent"
    # 두 팔이 아래쪽으로 모이므로 body는 아래쪽 (y > 0.5)
    assert body[1] > 0.5


def test_extrapolate_body_from_hand():
    """wrist에서 arm_angle 방향으로 외삽."""
    body = extrapolate_body_from_hand((0.5, 0.5), math.pi / 2, extrapolation=0.4)
    assert body[0] == pytest.approx(0.5, abs=1e-6)
    assert body[1] == pytest.approx(0.9, abs=1e-6)
