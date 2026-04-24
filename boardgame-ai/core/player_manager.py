"""플레이어 CRUD + 좌석 등록 공통 로직.

각 게임 FSM이 중복 구현하지 않도록 코어에서 관리.
게임 FSM은 PlayerManager.get_players()로 완성된 플레이어 리스트를 스냅샷으로 받아 시작.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from core.models import Player, SeatZone


@dataclass
class PlayerManagerState:
    players: list[Player] = field(default_factory=list)
    registering_player_id: str | None = None
    # pending_wrists: {"Right": (x,y)} 또는 {"Right": (x,y), "Left": (x,y)}
    pending_wrists: dict[str, tuple[float, float]] = field(default_factory=dict)


class PlayerManager:
    def __init__(self) -> None:
        self.state = PlayerManagerState()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_player(self, playername: str) -> str:
        """플레이어를 추가하고 player_id를 반환한다."""
        player_id = f"p_{uuid.uuid4().hex[:8]}"
        self.state.players.append(
            Player(
                player_id=player_id,
                playername=playername,
                seat_zone=None,
                registered_at=time.time(),
            )
        )
        return player_id

    def edit_playername(self, player_id: str, new_name: str) -> None:
        player = self._get_or_raise(player_id)
        player.playername = new_name

    def remove_player(self, player_id: str) -> None:
        self.state.players = [p for p in self.state.players if p.player_id != player_id]

    def get_players(self) -> list[Player]:
        """seat_zone=None인 플레이어가 있으면 ValueError."""
        unregistered = [p.player_id for p in self.state.players if p.seat_zone is None]
        if unregistered:
            raise ValueError(f"Players without seat_zone: {unregistered}")
        return list(self.state.players)

    # ------------------------------------------------------------------
    # 좌석 등록 sub-flow
    # ------------------------------------------------------------------

    def start_seat_registration(self, player_id: str) -> None:
        """지정 플레이어의 좌석 등록을 시작한다."""
        self._get_or_raise(player_id)
        self.state.registering_player_id = player_id
        self.state.pending_wrists = {}

    def record_hand(self, hand: str, wrist: tuple[float, float]) -> bool:
        """한 손의 wrist 좌표를 기록한다. 양손(Right+Left)이 모두 기록되면 True."""
        if self.state.registering_player_id is None:
            raise RuntimeError("No seat registration in progress")
        self.state.pending_wrists[hand] = wrist
        return "Right" in self.state.pending_wrists and "Left" in self.state.pending_wrists

    def finalize_seat(self) -> Player:
        """pending_wrists로 SeatZone을 조립해 플레이어에 등록하고 Player를 반환한다."""
        player_id = self.state.registering_player_id
        if player_id is None:
            raise RuntimeError("No seat registration in progress")
        if "Right" not in self.state.pending_wrists or "Left" not in self.state.pending_wrists:
            raise RuntimeError("Both hands must be recorded before finalizing")

        player = self._get_or_raise(player_id)
        player.seat_zone = SeatZone(
            right_hand_wrist=self.state.pending_wrists["Right"],
            left_hand_wrist=self.state.pending_wrists["Left"],
        )
        self.state.registering_player_id = None
        self.state.pending_wrists = {}
        return player

    def restart_seat_registration(self, player_id: str) -> None:
        """이미 등록된 플레이어의 좌석 재등록 — 기존 seat_zone을 초기화하고 다시 시작."""
        player = self._get_or_raise(player_id)
        player.seat_zone = None
        self.start_seat_registration(player_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_raise(self, player_id: str) -> Player:
        for p in self.state.players:
            if p.player_id == player_id:
                return p
        raise KeyError(f"Player not found: {player_id}")
