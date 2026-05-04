"""한밤의 늑대인간 비전 전용 데이터 타입.

모든 좌표는 정규화 float (0.0~1.0) — vision/schemas.py 규칙 준수.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vision.schemas import BBox

# YOLO 모델이 감지할 클래스 이름 집합 (학습 클래스명과 대소문자 일치)
ROLE_CLASSES: frozenset[str] = frozenset({
    "Werewolf",
    "Seer",
    "Robber",
    "Troublemaker",
    "Drunk",
    "Insomniac",
    "Villager",
    "Hunter",
    "Tanner",
    "Minion",
    "Doppelganger",
    "Mason",
})
BACK_CLASS: str = "Card_Back"
ALL_CARD_CLASSES: frozenset[str] = ROLE_CLASSES | {BACK_CLASS}


@dataclass
class CardDetRaw:
    """YOLO 단일 카드 감지 결과."""

    bbox: BBox
    cls_name: str  # ROLE_CLASSES 중 하나 또는 "card_back"
    conf: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox.to_dict(),
            "cls_name": self.cls_name,
            "conf": self.conf,
        }


@dataclass
class TrackedCard:
    """ByteTrack 으로 추적 중인 카드 1장의 상태.

    cls_name 은 마지막으로 앞면이 감지됐을 때의 역할 클래스.
    카드를 뒤집어도 ByteTrack track_id 와 cls_name 은 유지된다.
    """

    track_id: int
    bbox: BBox                 # 현재 프레임 위치 (정규화)
    cls_name: str | None       # 역할 클래스. 한 번도 앞면 감지 안 됐으면 None
    face_up: bool              # 현재 프레임에서 앞면 여부
    player_id: str | None      # 매칭된 player_id. None 이면 센터 카드
    card_index: int            # 플레이어 카드는 0, 센터 카드는 0/1/2 (좌→우)
    stable_frames: int         # 연속 추적 프레임 수
    just_flipped_up: bool = False  # face_down → face_up 전환이 이번 프레임인지 (1회성)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "bbox": self.bbox.to_dict(),
            "cls_name": self.cls_name,
            "face_up": self.face_up,
            "player_id": self.player_id,
            "card_index": self.card_index,
            "stable_frames": self.stable_frames,
            "just_flipped_up": self.just_flipped_up,
        }
