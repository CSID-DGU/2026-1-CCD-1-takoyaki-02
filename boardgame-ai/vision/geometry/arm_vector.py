"""팔 방향 추정 + 플레이어 중심점 외삽 유틸.

MediaPipe Hand 21 landmark에서 wrist(0)와 MIDDLE_MCP(9) 좌표를 사용해
팔이 뻗어나오는 방향(arm_angle)을 추정한다. wrist - middle_mcp 벡터는
손바닥의 반대 방향, 즉 팔이 뻗어 들어오는 방향을 가리킨다.
"""

from __future__ import annotations

import math

_WRIST = 0
_MIDDLE_MCP = 9

# 양손 wrist에서 몸 쪽으로 외삽할 거리 (정규화 좌표).
# 화면 밖이어도 OK — 좌석 위치는 화면 가장자리/외부에 있다.
_BODY_EXTRAPOLATION = 0.4

# 두 팔 각도 차이가 이 값보다 크면 "stretched"(일직선), 아니면 "bent"(꺾임).
# 일직선 = π에 가까움, V자 꺾임 = 2π/3 미만.
_STRETCHED_THRESHOLD = 2.0  # ≈ 114° 이상이면 stretched로 본다


def compute_arm_angle(landmarks_21: list[tuple[float, float]]) -> float:
    """wrist(0) - middle_mcp(9) 벡터의 각도 (atan2 기준, [-π, π]).

    팔이 뻗어 들어오는 방향. 손바닥이 화면 위쪽을 향하면 wrist가 mcp보다 아래
    (y가 큰 쪽) → atan2 양수. 즉 "+y는 아래"라는 화면 좌표계에서 그대로 사용.
    """
    if len(landmarks_21) < 21:
        return 0.0
    wx, wy = landmarks_21[_WRIST]
    mx, my = landmarks_21[_MIDDLE_MCP]
    return math.atan2(wy - my, wx - mx)


def angular_diff(a: float, b: float) -> float:
    """두 각도의 최소 절대 차 [0, π]. 각도 wrap-around 안전."""
    d = (a - b) % (2 * math.pi)
    if d > math.pi:
        d = 2 * math.pi - d
    return d


def _circular_mean(angles: list[float]) -> float:
    """단위원 위 평균(원형 평균)."""
    sx = sum(math.cos(a) for a in angles)
    sy = sum(math.sin(a) for a in angles)
    return math.atan2(sy, sx)


def estimate_body_xy(
    right_wrist: tuple[float, float],
    right_angle: float,
    left_wrist: tuple[float, float],
    left_angle: float,
    extrapolation: float = _BODY_EXTRAPOLATION,
) -> tuple[tuple[float, float], str]:
    """등록 시 양손 정보로 플레이어 중심점(몸 위치)과 자세를 추정한다.

    Returns
    -------
    (body_xy, posture) — body_xy는 (x, y), posture ∈ {"stretched", "bent"}.

    case A — stretched (양팔 일직선): 두 arm_angle이 거의 반대 방향(차이 ≈ π).
      플레이어는 두 wrist 중점에서 평균 방향으로 외삽한 위치에 있다고 본다.
    case B — bent (V자 꺾임): arm_angle이 비슷한 방향. 두 팔이 V로 모이며
      합벡터 방향이 몸통 방향과 일치한다고 본다.
    """
    diff = angular_diff(right_angle, left_angle)
    posture = "stretched" if diff >= _STRETCHED_THRESHOLD else "bent"

    mid_x = (right_wrist[0] + left_wrist[0]) / 2.0
    mid_y = (right_wrist[1] + left_wrist[1]) / 2.0

    if posture == "stretched":
        # 양팔이 일직선이면 평균 각도가 그대로 몸 방향
        body_angle = _circular_mean([right_angle, left_angle])
    else:
        # V자 꺾임: 두 팔이 모이는 합벡터 방향
        body_angle = _circular_mean([right_angle, left_angle])

    body_x = mid_x + extrapolation * math.cos(body_angle)
    body_y = mid_y + extrapolation * math.sin(body_angle)
    return (body_x, body_y), posture


def extrapolate_body_from_hand(
    wrist_xy: tuple[float, float],
    arm_angle: float,
    extrapolation: float = _BODY_EXTRAPOLATION,
) -> tuple[float, float]:
    """게임 중 손 한 개에서 그 사람의 몸 추정 위치로 외삽.

    트랙 첫 프레임의 wrist + arm_angle로 body 외삽 → 등록된 body_xy와 비교.
    """
    bx = wrist_xy[0] + extrapolation * math.cos(arm_angle)
    by = wrist_xy[1] + extrapolation * math.sin(arm_angle)
    return (bx, by)
