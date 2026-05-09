"""요트다이스 전용 비전 데이터 타입.

모든 좌표는 정규화 float (0.0~1.0) — vision/schemas.py 규칙 준수.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from vision.schemas import BBox, FramePerception, HandDet


@dataclass
class DiceState:
    """주사위 하나의 트래킹 상태."""

    track_id: int
    bbox: BBox
    center: tuple[float, float]
    motion_score: float
    stable_frames: int
    pip_count: int | None = None  # 안정 후 확정된 눈 수

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "bbox": self.bbox.to_dict(),
            "center": list(self.center),
            "motion_score": self.motion_score,
            "stable_frames": self.stable_frames,
            "pip_count": self.pip_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DiceState:
        return cls(
            track_id=int(d["track_id"]),
            bbox=BBox.from_dict(d["bbox"]),
            center=tuple(d["center"]),
            motion_score=float(d["motion_score"]),
            stable_frames=int(d["stable_frames"]),
            pip_count=d.get("pip_count"),
        )


@dataclass
class YachtFramePerception(FramePerception):
    """요트다이스 전용 확장 FramePerception.

    공용 필드(frame_id, ts, image_hw, hands, phase_hints)는 부모에서 상속.
    주사위·트레이 관련 필드만 추가.
    """

    tray: BBox | None = None
    tray_inner: BBox | None = None
    roll_tray: BBox | None = None
    dice: list[DiceState] = field(default_factory=list)
    roll_actor_id: str | None = None
    roll_just_confirmed: bool = False

    def dice_all_stable(self, stabilization_frames: int) -> bool:
        if not self.dice:
            return False
        return all(d.stable_frames >= stabilization_frames for d in self.dice)

    def dice_values(self) -> list[int | None]:
        return [d.pip_count for d in self.dice]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update({
            "tray": self.tray.to_dict() if self.tray else None,
            "tray_inner": self.tray_inner.to_dict() if self.tray_inner else None,
            "roll_tray": self.roll_tray.to_dict() if self.roll_tray else None,
            "dice": [ds.to_dict() for ds in self.dice],
            "roll_actor_id": self.roll_actor_id,
            "roll_just_confirmed": self.roll_just_confirmed,
        })
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> YachtFramePerception:
        return cls(
            frame_id=int(d["frame_id"]),
            ts=float(d["ts"]),
            image_hw=tuple(d["image_hw"]),
            hands=[HandDet.from_dict(x) for x in d.get("hands", [])],
            phase_hints=dict(d.get("phase_hints", {})),
            tray=BBox.from_dict(d["tray"]) if d.get("tray") else None,
            tray_inner=BBox.from_dict(d["tray_inner"]) if d.get("tray_inner") else None,
            roll_tray=BBox.from_dict(d["roll_tray"]) if d.get("roll_tray") else None,
            dice=[DiceState.from_dict(x) for x in d.get("dice", [])],
            roll_actor_id=d.get("roll_actor_id"),
            roll_just_confirmed=bool(d.get("roll_just_confirmed", False)),
        )
