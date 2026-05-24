"""프론트엔드로 broadcast할 state 스냅샷 빌더."""

from __future__ import annotations

import math

from core.models import Player


def _body_to_position(body_xy: tuple[float, float]) -> float:
    """body_xy(0..1 정규화 카메라 좌표) → 둘레 위치 0..1 (시계방향, top-left가 0).

    프론트 TableVisualization의 perimeterPoint 규약과 일치:
      t=0   → top-left, 시계방향으로 증가 (top → right → bottom → left)
    화면 중심 기준 각도를 사각형 둘레로 사영해 매핑한다.
    """
    x, y = body_xy
    dx, dy = x - 0.5, y - 0.5
    # atan2: -π..π. top(-y)이 -π/2.
    # 시계방향으로 top-left부터 시작하려면 (angle + 3π/4)을 [0, 2π)로 wrap.
    angle = math.atan2(dy, dx)
    t = (angle + 3 * math.pi / 4) / (2 * math.pi)
    return t % 1.0


def build_state_snapshot(
    players: list[Player],
    phase: str,
    registering_player_id: str | None = None,
    seat_step: str = "idle",
    sound: str | None = None,
    sound_seq: int = 0,
    game_state: dict | None = None,
    gesture_confirmed: str | None = None,
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
                # 좌석 등록 후에만 채워짐. 프론트는 None이면 등록 순서로 임시 분배.
                "position": (
                    _body_to_position(p.seat_zone.body_xy)
                    if p.seat_zone is not None
                    else None
                ),
            }
            for p in players
        ],
        # 1회성 trigger: 프론트가 sound_seq 값 변경 감지 시 재생
        "sound": sound,
        "sound_seq": sound_seq,
        # 1회성 trigger: OK 사인 감지 시 확인한 player_id
        "gesture_confirmed": gesture_confirmed,
    }
    if game_state is not None:
        result["game_state"] = game_state
    return result
