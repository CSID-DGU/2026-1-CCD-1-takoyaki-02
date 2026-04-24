"""한밤의 늑대인간 게임 상태."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from games.werewolf.ontology import WerewolfPhase

DEFAULT_DISCUSSION_SECONDS = 300


@dataclass
class CardAnchor:
    """카드 위치 기준점. 비전팀이 카드 인식 시 등록하고 사용."""

    owner_id: str | None  # player_id. None이면 center card
    card_index: int       # 플레이어 카드는 0, 센터 카드는 0/1/2
    x: float              # 정규화 좌표 0.0~1.0
    y: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "card_index": self.card_index,
            "x": self.x,
            "y": self.y,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CardAnchor:
        return cls(
            owner_id=d.get("owner_id"),
            card_index=int(d["card_index"]),
            x=float(d["x"]),
            y=float(d["y"]),
        )


@dataclass
class NightAction:
    """야간 행동 기록. resolve_night_action()에서 소비한다."""

    actor_id: str
    action_type: str       # 역할별 행동 식별자 (예: "seer_peek_player")
    target_ids: list[str]  # 대상 player_id 또는 "center_0"/"center_1"/"center_2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "action_type": self.action_type,
            "target_ids": list(self.target_ids),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NightAction:
        return cls(
            actor_id=d["actor_id"],
            action_type=d["action_type"],
            target_ids=list(d["target_ids"]),
        )


@dataclass
class Swap:
    """카드 교환 기록. ROBBER·TROUBLEMAKER 행동 결과."""

    from_id: str   # player_id 또는 "center_0"/"center_1"/"center_2"
    to_id: str
    from_role: str  # WerewolfRole.value (교환 전 역할)
    to_role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "from_role": self.from_role,
            "to_role": self.to_role,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Swap:
        return cls(
            from_id=d["from_id"],
            to_id=d["to_id"],
            from_role=d["from_role"],
            to_role=d["to_role"],
        )


@dataclass
class WerewolfPlayerState:
    player_id: str
    original_role: str          # WerewolfRole.value — 게임 시작 시 배정
    current_role: str           # ROBBER·TROUBLEMAKER 행동 후 달라질 수 있음
    voted_for: str | None = None  # 투표 대상 player_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "original_role": self.original_role,
            "current_role": self.current_role,
            "voted_for": self.voted_for,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WerewolfPlayerState:
        return cls(
            player_id=d["player_id"],
            original_role=d["original_role"],
            current_role=d["current_role"],
            voted_for=d.get("voted_for"),
        )


@dataclass
class WerewolfGameState:
    players: list[WerewolfPlayerState]
    player_order: list[str]            # player_id 순서
    center_cards: list[str]            # 3개, WerewolfRole.value
    anchors: list[CardAnchor]          # 비전팀이 등록한 카드 위치
    night_actions: list[NightAction]   # 야간 행동 로그
    swaps: list[Swap]                  # 카드 교환 로그
    timer_remaining: int               # DAY_DISCUSSION 남은 시간(초)
    phase: str                         # WerewolfPhase value
    state_version: int = 0
    winner: str | None = None          # "werewolf" | "village" | "tanner" | None

    @classmethod
    def new(
        cls,
        players: list[WerewolfPlayerState],
        center_cards: list[str],
    ) -> WerewolfGameState:
        """플레이어와 센터 카드로 초기 상태를 생성한다."""
        return cls(
            players=players,
            player_order=[p.player_id for p in players],
            center_cards=center_cards,
            anchors=[],
            night_actions=[],
            swaps=[],
            timer_remaining=DEFAULT_DISCUSSION_SECONDS,
            phase=WerewolfPhase.NIGHT_START.value,
        )

    def get_player(self, player_id: str) -> WerewolfPlayerState:
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise KeyError(f"Player not found: {player_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "players": [p.to_dict() for p in self.players],
            "player_order": list(self.player_order),
            "center_cards": list(self.center_cards),
            "anchors": [a.to_dict() for a in self.anchors],
            "night_actions": [n.to_dict() for n in self.night_actions],
            "swaps": [s.to_dict() for s in self.swaps],
            "timer_remaining": self.timer_remaining,
            "phase": self.phase,
            "state_version": self.state_version,
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WerewolfGameState:
        return cls(
            players=[WerewolfPlayerState.from_dict(p) for p in d["players"]],
            player_order=list(d["player_order"]),
            center_cards=list(d["center_cards"]),
            anchors=[CardAnchor.from_dict(a) for a in d.get("anchors", [])],
            night_actions=[NightAction.from_dict(n) for n in d.get("night_actions", [])],
            swaps=[Swap.from_dict(s) for s in d.get("swaps", [])],
            timer_remaining=int(d["timer_remaining"]),
            phase=d["phase"],
            state_version=int(d.get("state_version", 0)),
            winner=d.get("winner"),
        )
