"""프론트엔드로 broadcast할 state 스냅샷 빌더."""

from __future__ import annotations

from core.models import Player


def build_state_snapshot(
    players: list[Player],
    phase: str,
    registering_player_id: str | None = None,
    seat_step: str = "idle",
    sound: str | None = None,
    game_state: dict | None = None,
) -> dict:
    result: dict = {
        "phase": phase,
        "registering_player_id": registering_player_id,
        # idle | right_pending | right_done | completed
        "seat_step": seat_step,
        "players": [
            {
                "player_id": p.player_id,
                "playername": p.playername,
                "registered": p.seat_zone is not None,
            }
            for p in players
        ],
        # 1회성 trigger: 프론트가 사운드 재생 후 무시
        "sound": sound,
    }
    if game_state is not None:
        result["game_state"] = game_state
    return result
