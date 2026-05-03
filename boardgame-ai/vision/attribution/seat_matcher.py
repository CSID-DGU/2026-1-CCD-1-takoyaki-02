"""팔 방향 기반 플레이어 좌석 매칭.

신규 HandTrack이 발생했을 때 트랙 첫 프레임의 wrist 좌표 + arm_angle로
등록된 플레이어 SeatZone과 비교해 player_id를 결정한다.

신호 (가중합, 낮을수록 좋음):
  1. arm_angle 차이 (0~π)             — 1차, 가장 강함
  2. entry wrist 위치 거리             — 2차, 손이 가운데 모이기 전 분리
  3. 손 → 외삽 body_xy ↔ 등록 body_xy 거리 — 3차, 같은 사람 두 손 검증

handedness가 일치하는 ArmAnchor만 비교. 매칭 결과 None 금지 — 후보 풀이
비지 않으면 항상 best player_id 반환. 양손 모두 다른 활성 트랙에 잡힌
플레이어는 후보에서 제외.
"""

from __future__ import annotations

import math

from core.models import Player
from vision.geometry.arm_vector import angular_diff, extrapolate_body_from_hand

# 가중치
_W_ANGLE = 0.5  # arm_angle 차이 (정규화 0~1, π 나눔)
_W_ENTRY = 0.3  # entry wrist 위치 거리 (정규화)
_W_BODY = 0.2  # body_xy 외삽 거리 (정규화)


def match_player_by_arm(
    handedness: str,
    entry_wrist_xy: tuple[float, float],
    entry_arm_angle: float,
    players: list[Player],
    excluded_player_ids: set[str] | None = None,
) -> tuple[str | None, float]:
    """팔 방향 + entry 위치 + body 외삽으로 player_id 결정.

    Parameters
    ----------
    handedness        : "Right" | "Left"
    entry_wrist_xy    : 트랙 첫 프레임 wrist (정규화)
    entry_arm_angle   : 트랙 첫 프레임 arm_angle (radians)
    players           : 등록된 플레이어 리스트 (seat_zone 채워진 플레이어만 후보)
    excluded_player_ids : 후보에서 제외할 player_id 집합 (양손 다른 트랙에 잡힌 사람)

    Returns
    -------
    (player_id | None, best_score)
    풀이 비지 않으면 항상 best 반환. 풀이 비면(seat_zone 등록자 0명) None.
    """
    excluded = excluded_player_ids or set()

    best_id: str | None = None
    best_score = float("inf")

    for player in players:
        if player.player_id in excluded:
            continue
        if player.seat_zone is None:
            continue
        anchor = player.seat_zone.right_arm if handedness == "Right" else player.seat_zone.left_arm
        body_xy = player.seat_zone.body_xy

        # 1. 각도 차이 정규화 (0~π → 0~1)
        d_angle = angular_diff(entry_arm_angle, anchor.arm_angle) / math.pi

        # 2. entry wrist 거리 (대략 0~1.4)
        d_entry = math.hypot(
            entry_wrist_xy[0] - anchor.wrist_xy[0],
            entry_wrist_xy[1] - anchor.wrist_xy[1],
        )

        # 3. body 외삽 거리 — 새 손이 외삽한 몸 위치 vs 등록 body_xy
        est_body = extrapolate_body_from_hand(entry_wrist_xy, entry_arm_angle)
        d_body = math.hypot(est_body[0] - body_xy[0], est_body[1] - body_xy[1])

        score = _W_ANGLE * d_angle + _W_ENTRY * d_entry + _W_BODY * d_body
        if score < best_score:
            best_score = score
            best_id = player.player_id

    return best_id, best_score


def players_with_both_hands_tracked(
    active_tracks,  # list[HandTrack]
) -> set[str]:
    """양손이 모두 활성 트랙에 잡힌 플레이어 ID 집합.

    각 활성 트랙의 confirmed_handedness + confirmed_player_id를 조합해
    한 player_id에 대해 Right/Left 모두 잡혀있으면 그 사람을 반환.
    """
    sides_by_player: dict[str, set[str]] = {}
    for trk in active_tracks:
        pid = trk.confirmed_player_id
        hd = trk.confirmed_handedness
        if pid is None or hd is None:
            continue
        sides_by_player.setdefault(pid, set()).add(hd)

    return {pid for pid, sides in sides_by_player.items() if "Right" in sides and "Left" in sides}
