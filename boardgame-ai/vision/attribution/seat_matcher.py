"""handedness + wrist 좌표 → player_id 매칭.

등록된 SeatZone(right_hand_wrist, left_hand_wrist)과 감지된 손의
wrist 좌표 사이 Euclidean distance로 플레이어를 특정.
"""

from __future__ import annotations

import math

from core.constants import DEFAULT_PARAMS
from core.models import Player
from vision.schemas import HandDet


class SeatMatcher:
    """
    Parameters
    ----------
    wrist_distance_min_norm : 허용 최소 거리 (이보다 가까우면 같은 손으로 간주해 skip)
    wrist_distance_max_norm : 허용 최대 거리 (이보다 멀면 매칭 실패)
    """

    def __init__(
        self,
        wrist_distance_min_norm: float | None = None,
        wrist_distance_max_norm: float | None = None,
    ) -> None:
        self._min = wrist_distance_min_norm or float(DEFAULT_PARAMS["wrist_distance_min_norm"])
        self._max = wrist_distance_max_norm or float(DEFAULT_PARAMS["wrist_distance_max_norm"])

    def match(self, hand: HandDet, players: list[Player]) -> str | None:
        """
        Returns
        -------
        player_id 또는 None (매칭 실패 / seat_zone 미등록)
        """
        best_id: str | None = None
        best_dist = float("inf")

        for player in players:
            if player.seat_zone is None:
                continue

            if hand.handedness == "Right":
                ref = player.seat_zone.right_hand_wrist
            else:
                ref = player.seat_zone.left_hand_wrist

            d = _euclidean(hand.wrist_xy, ref)
            if d < self._min or d > self._max:
                continue
            if d < best_dist:
                best_dist = d
                best_id = player.player_id

        return best_id


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
