"""한밤의 늑대인간 승리 판정."""

from __future__ import annotations

from games.werewolf.ontology import WEREWOLF_TEAM, WerewolfRole
from games.werewolf.state import WerewolfGameState


def tally_votes(state: WerewolfGameState) -> dict[str, int]:
    """각 플레이어의 득표 수를 반환한다."""
    counts: dict[str, int] = {}
    for p in state.players:
        if p.voted_for:
            counts[p.voted_for] = counts.get(p.voted_for, 0) + 1
    return counts


def find_executed(state: WerewolfGameState) -> list[str]:
    """가장 많이 득표한 플레이어를 반환한다.

    동률이면 모두 포함. 3인 이상에서 전원이 1표씩 분산되면 아무도 처형 안 됨.
    """
    counts = tally_votes(state)
    if not counts:
        return []
    max_votes = max(counts.values())
    # 3인 이상에서 최대 득표가 1표 = 전원 분산 → 처형 없음
    if max_votes == 1 and len(state.players) >= 3:
        return []
    return [pid for pid, cnt in counts.items() if cnt == max_votes]


def judge_winner(state: WerewolfGameState) -> str:
    """승리 팀을 반환한다.

    Returns:
        "werewolf" | "village" | "tanner"
    """
    executed = find_executed(state)

    # 태너가 처형되면 태너 승리 (최우선)
    for pid in executed:
        if state.get_player(pid).current_role == WerewolfRole.TANNER:
            return "tanner"

    werewolf_players = [
        p for p in state.players if p.current_role in WEREWOLF_TEAM
    ]
    executed_werewolves = [
        pid for pid in executed if state.get_player(pid).current_role in WEREWOLF_TEAM
    ]

    if werewolf_players:
        # 늑대인간이 존재하는 게임
        return "village" if executed_werewolves else "werewolf"
    else:
        # 늑대인간이 없는 게임: 아무도 처형되지 않으면 마을 승리
        return "village" if not executed else "werewolf"
