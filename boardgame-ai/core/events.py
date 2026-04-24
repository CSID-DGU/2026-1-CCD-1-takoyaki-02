"""비전 ↔ FSM 이벤트와 컨텍스트.

event_type과 fsm_state는 문자열로 처리 (core는 구체 게임을 모름).
각 게임 팀이 자기 EventType/Phase enum 값을 문자열로 넣어 사용.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameEvent:
    event_type: str  # CommonEventType.value 또는 게임별 enum value
    actor_id: str | None
    confidence: float
    frame_id: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "confidence": self.confidence,
            "frame_id": self.frame_id,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GameEvent:
        return cls(
            event_type=d["event_type"],
            actor_id=d.get("actor_id"),
            confidence=float(d["confidence"]),
            frame_id=int(d["frame_id"]),
            data=dict(d.get("data", {})),
        )


@dataclass
class FusionContext:
    fsm_state: str  # CommonPhase 또는 게임별 Phase value
    game_type: str | None  # "yacht" | "werewolf" | None
    active_player: str | None
    allowed_actors: list[str]
    expected_events: list[str]  # event_type value 문자열들
    reject_events: list[str] = field(default_factory=list)
    valid_targets: dict[str, Any] | None = None
    zones: dict[str, Any] = field(default_factory=dict)
    anchors: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def expects(self, event_type: str) -> bool:
        if event_type in self.reject_events:
            return False
        return event_type in self.expected_events

    def is_actor_allowed(self, player_id: str) -> bool:
        return player_id in self.allowed_actors

    def to_dict(self) -> dict[str, Any]:
        return {
            "fsm_state": self.fsm_state,
            "game_type": self.game_type,
            "active_player": self.active_player,
            "allowed_actors": list(self.allowed_actors),
            "expected_events": list(self.expected_events),
            "reject_events": list(self.reject_events),
            "valid_targets": self.valid_targets,
            "zones": dict(self.zones),
            "anchors": dict(self.anchors),
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FusionContext:
        return cls(
            fsm_state=d["fsm_state"],
            game_type=d.get("game_type"),
            active_player=d.get("active_player"),
            allowed_actors=list(d.get("allowed_actors", [])),
            expected_events=list(d.get("expected_events", [])),
            reject_events=list(d.get("reject_events", [])),
            valid_targets=d.get("valid_targets"),
            zones=dict(d.get("zones", {})),
            anchors=dict(d.get("anchors", {})),
            params=dict(d.get("params", {})),
        )
