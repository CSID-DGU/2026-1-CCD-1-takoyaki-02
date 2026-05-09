"""프레임 단위 비전 인지 결과 공용 데이터 구조.

모든 좌표는 정규화 float64 (0.0 ~ 1.0) — core 규칙 준수.
외부 라이브러리(numpy 등) 미사용. 순수 Python dataclass.

요트다이스 전용 타입(DiceState, YachtFramePerception)은 vision/yacht/schemas.py 에 있음.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BBox:
    """정규화 바운딩박스 (0.0~1.0)."""

    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_name: str

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def w(self) -> float:
        return self.x2 - self.x1

    @property
    def h(self) -> float:
        return self.y2 - self.y1

    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)

    def iou(self, other: BBox) -> float:
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter == 0.0:
            return 0.0
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0

    def contains_point(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def to_dict(self) -> dict[str, Any]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "conf": self.conf,
            "cls_name": self.cls_name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BBox:
        return cls(
            x1=float(d["x1"]),
            y1=float(d["y1"]),
            x2=float(d["x2"]),
            y2=float(d["y2"]),
            conf=float(d["conf"]),
            cls_name=str(d["cls_name"]),
        )


@dataclass
class YoloDet:
    """YOLO 단일 감지 결과."""

    cls_name: str
    bbox: BBox
    track_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cls_name": self.cls_name,
            "bbox": self.bbox.to_dict(),
            "track_id": self.track_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> YoloDet:
        return cls(
            cls_name=str(d["cls_name"]),
            bbox=BBox.from_dict(d["bbox"]),
            track_id=d.get("track_id"),
        )


@dataclass
class HandDet:
    """MediaPipe 손 감지 결과."""

    handedness: str  # "Right" | "Left"
    wrist_xy: tuple[float, float]  # landmark[0], 정규화
    landmarks_21: list[tuple[float, float]]  # 21개 landmark (x, y), 정규화
    gesture: str | None = None  # "v_sign"|"ok_sign"|"grab"|"release"|"neutral"
    player_id: str | None = None  # SeatMatcher 결과
    arm_angle: float | None = None  # wrist - middle_mcp(9) 벡터 각도 (radians)

    def to_dict(self) -> dict[str, Any]:
        return {
            "handedness": self.handedness,
            "wrist_xy": list(self.wrist_xy),
            "landmarks_21": [list(lm) for lm in self.landmarks_21],
            "gesture": self.gesture,
            "player_id": self.player_id,
            "arm_angle": self.arm_angle,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HandDet:
        return cls(
            handedness=str(d["handedness"]),
            wrist_xy=tuple(d["wrist_xy"]),
            landmarks_21=[tuple(lm) for lm in d["landmarks_21"]],
            gesture=d.get("gesture"),
            player_id=d.get("player_id"),
            arm_angle=d.get("arm_angle"),
        )


@dataclass
class FramePerception:
    """프레임 단위 공용 인지 스냅샷. FusionEngine의 입력.

    요트다이스 전용 필드(tray, dice 등)는 YachtFramePerception(vision/yacht/schemas.py)에 있음.
    """

    frame_id: int
    ts: float
    image_hw: tuple[int, int]  # (height, width)
    hands: list[HandDet] = field(default_factory=list)
    phase_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "ts": self.ts,
            "image_hw": list(self.image_hw),
            "hands": [h.to_dict() for h in self.hands],
            "phase_hints": self.phase_hints,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FramePerception:
        return cls(
            frame_id=int(d["frame_id"]),
            ts=float(d["ts"]),
            image_hw=tuple(d["image_hw"]),
            hands=[HandDet.from_dict(x) for x in d.get("hands", [])],
            phase_hints=dict(d.get("phase_hints", {})),
        )
