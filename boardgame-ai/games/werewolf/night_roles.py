"""야간 행동 처리 순수 함수.

각 함수는 state를 직접 수정하고 플레이어에게 보여줄 정보(visible_info)를 반환한다.
"""

from __future__ import annotations

from games.werewolf.state import NightAction, Swap, WerewolfGameState


def resolve_seer_peek(
    state: WerewolfGameState,
    actor_id: str,
    target_id: str,
    card_index: int = 0,
) -> dict[str, str]:
    """예언자가 플레이어 카드 또는 센터 카드를 들여다본다.

    Returns:
        {target_id: role_value}
    """
    if target_id.startswith("center_"):
        idx = int(target_id.split("_")[1])
        role = state.center_cards[idx]
        action_type = "seer_peek_center"
    else:
        role = state.get_player(target_id).current_role
        action_type = "seer_peek_player"

    state.night_actions.append(
        NightAction(actor_id=actor_id, action_type=action_type, target_ids=[target_id])
    )
    return {target_id: role}


def resolve_robber_swap(
    state: WerewolfGameState,
    actor_id: str,
    target_id: str,
) -> dict[str, str]:
    """도둑이 대상 플레이어의 카드를 가져가고 자신의 카드를 준다.

    Returns:
        {actor_id: new_role}  — 도둑이 훔친 후 자신의 새 역할
    """
    robber = state.get_player(actor_id)
    target = state.get_player(target_id)

    state.swaps.append(
        Swap(
            from_id=actor_id,
            to_id=target_id,
            from_role=robber.current_role,
            to_role=target.current_role,
        )
    )
    robber.current_role, target.current_role = target.current_role, robber.current_role
    state.night_actions.append(
        NightAction(actor_id=actor_id, action_type="robber_swap", target_ids=[target_id])
    )
    return {actor_id: robber.current_role}


def resolve_troublemaker_swap(
    state: WerewolfGameState,
    actor_id: str,
    from_id: str,
    to_id: str,
) -> None:
    """말썽꾼이 두 플레이어의 카드를 교환한다. 내용은 확인하지 않는다."""
    p1 = state.get_player(from_id)
    p2 = state.get_player(to_id)

    state.swaps.append(
        Swap(
            from_id=from_id,
            to_id=to_id,
            from_role=p1.current_role,
            to_role=p2.current_role,
        )
    )
    p1.current_role, p2.current_role = p2.current_role, p1.current_role
    state.night_actions.append(
        NightAction(
            actor_id=actor_id,
            action_type="troublemaker_swap",
            target_ids=[from_id, to_id],
        )
    )


def resolve_drunk_swap(
    state: WerewolfGameState,
    actor_id: str,
    center_id: str,
) -> None:
    """술꾼이 자신의 카드를 센터 카드와 교환한다. 내용은 확인하지 않는다."""
    idx = int(center_id.split("_")[1])
    drunk = state.get_player(actor_id)

    state.swaps.append(
        Swap(
            from_id=actor_id,
            to_id=center_id,
            from_role=drunk.current_role,
            to_role=state.center_cards[idx],
        )
    )
    drunk.current_role, state.center_cards[idx] = state.center_cards[idx], drunk.current_role
    state.night_actions.append(
        NightAction(actor_id=actor_id, action_type="drunk_swap", target_ids=[center_id])
    )


def resolve_insomniac_peek(
    state: WerewolfGameState,
    actor_id: str,
) -> dict[str, str]:
    """불면증환자가 자신의 현재 카드를 확인한다.

    Returns:
        {actor_id: current_role}
    """
    player = state.get_player(actor_id)
    state.night_actions.append(
        NightAction(actor_id=actor_id, action_type="insomniac_peek", target_ids=[actor_id])
    )
    return {actor_id: player.current_role}
