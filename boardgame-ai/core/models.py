"""게임 불문 공통 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SeatZone:
    """양손 등록 기반 플레이어 식별용 좌표.

    등록: 오른손 V-sign 좌표 P_R, 왼손 OK-sign 좌표 P_L을 저장.
    매칭: 런타임에 감지된 손의 handedness가 Right면 각 플레이어의 P_R과
          Euclidean distance 비교해 최소인 플레이어가 주인. Left면 P_L.

    좌표는 정규화 float64 (0.0 ~ 1.0).
    """

    right_hand_wrist: tuple[float, float]
    left_hand_wrist: tuple[float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "right_hand_wrist": list(self.right_hand_wrist),
            "left_hand_wrist": list(self.left_hand_wrist),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SeatZone:
        return cls(
            right_hand_wrist=tuple(d["right_hand_wrist"]),
            left_hand_wrist=tuple(d["left_hand_wrist"]),
        )


@dataclass
class Player:
    player_id: str
    playername: str
    seat_zone: SeatZone | None = None
    registered_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "playername": self.playername,
            "seat_zone": self.seat_zone.to_dict() if self.seat_zone is not None else None,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Player:
        seat_zone = SeatZone.from_dict(d["seat_zone"]) if d.get("seat_zone") is not None else None
        return cls(
            player_id=d["player_id"],
            playername=d["playername"],
            seat_zone=seat_zone,
            registered_at=float(d.get("registered_at", 0.0)),
        )
