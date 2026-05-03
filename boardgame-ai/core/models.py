"""게임 불문 공통 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ArmAnchor:
    """팔 방향 기반 한쪽 팔 기준점.

    등록 시점에 MediaPipe HandLandmarker 21 landmark에서 직접 추정한 값.
    wrist_xy: landmark[0]. arm_angle: wrist - middle_mcp(9) 벡터의 각도(rad).
    팔이 뻗어 들어오는 방향 = 손바닥의 반대 방향.
    """

    handedness: str  # "Right" | "Left"
    wrist_xy: tuple[float, float]  # 정규화 (0.0~1.0)
    arm_angle: float  # atan2(wrist.y - mcp.y, wrist.x - mcp.x), [-π, π]

    def to_dict(self) -> dict[str, Any]:
        return {
            "handedness": self.handedness,
            "wrist_xy": list(self.wrist_xy),
            "arm_angle": self.arm_angle,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArmAnchor:
        return cls(
            handedness=str(d["handedness"]),
            wrist_xy=tuple(d["wrist_xy"]),
            arm_angle=float(d["arm_angle"]),
        )


@dataclass
class SeatZone:
    """팔 방향 기반 플레이어 좌석 앵커.

    등록: 오른손 V사인 + 왼손 OK사인 순차 캡처 시점에 HandLandmarker로 측정.
    매칭: 새 HandTrack 발생 시 1회만 wrist + arm_angle + body_xy 비교.

    body_xy는 두 팔 정보로 외삽한 플레이어 몸 위치(화면 밖 가능).
    posture는 등록 자세: "stretched"(양팔 일직선) | "bent"(V자 꺾임).
    """

    right_arm: ArmAnchor
    left_arm: ArmAnchor
    body_xy: tuple[float, float]
    posture: str  # "stretched" | "bent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "right_arm": self.right_arm.to_dict(),
            "left_arm": self.left_arm.to_dict(),
            "body_xy": list(self.body_xy),
            "posture": self.posture,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SeatZone:
        return cls(
            right_arm=ArmAnchor.from_dict(d["right_arm"]),
            left_arm=ArmAnchor.from_dict(d["left_arm"]),
            body_xy=tuple(d["body_xy"]),
            posture=str(d["posture"]),
        )


@dataclass
class Player:
    player_id: str
    playername: str | None = None  # 임시 등록 중이면 None, finalize 후 채워짐
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
            playername=d.get("playername"),
            seat_zone=seat_zone,
            registered_at=float(d.get("registered_at", 0.0)),
        )
