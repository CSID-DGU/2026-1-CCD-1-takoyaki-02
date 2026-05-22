"""한밤의 늑대인간 FSM 타이머 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from games.werewolf.fsm import WerewolfFSM
from games.werewolf.ontology import WerewolfPhase
from games.werewolf.state import WerewolfPlayerState


def _make_fsm(roles: list[str], broadcast=None) -> WerewolfFSM:
    if broadcast is None:

        async def _noop(_msg):
            pass

        broadcast = _noop
    players = [
        WerewolfPlayerState(player_id=f"p_{i}", original_role=r, current_role=r)
        for i, r in enumerate(roles)
    ]
    return WerewolfFSM(
        players=players,
        center_cards=["villager", "villager", "villager"],
        broadcast=broadcast,
    )


# ── 패시브 타이머 ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_passive_werewolf_phase_auto_advances() -> None:
    """night_werewolf 진입 후 타이머 경과 시 자동 전환."""
    fsm = _make_fsm(["werewolf"])

    with patch("games.werewolf.fsm.PASSIVE_PHASE_DURATION", 0):
        fsm.start()
        await asyncio.sleep(0.05)

    assert fsm.state.phase != WerewolfPhase.NIGHT_WEREWOLF.value


@pytest.mark.anyio
async def test_passive_timer_skips_if_phase_already_changed() -> None:
    """phase가 이미 변경된 경우 패시브 타이머 콜백이 전환 skip."""
    broadcast_msgs: list = []

    async def record(msg):
        broadcast_msgs.append(msg)

    fsm = _make_fsm(["werewolf"], broadcast=record)
    fsm.state.phase = WerewolfPhase.DAY_DISCUSSION.value

    initial_version = fsm.state.state_version
    with patch("games.werewolf.fsm.PASSIVE_PHASE_DURATION", 0):
        await fsm._run_passive_timer(WerewolfPhase.NIGHT_WEREWOLF)

    assert fsm.state.phase == WerewolfPhase.DAY_DISCUSSION.value
    assert fsm.state.state_version == initial_version


# ── 액티브 타이머 ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_active_timeout_advances_phase_when_no_event() -> None:
    """액티브 역할 타임아웃 경과 시 강제 전환."""
    fsm = _make_fsm(["seer"])

    with patch("games.werewolf.fsm.ACTIVE_PHASE_TIMEOUT", 0):
        fsm.start()
        await asyncio.sleep(0.05)

    assert fsm.state.phase != WerewolfPhase.NIGHT_SEER.value


@pytest.mark.anyio
async def test_active_timer_skips_if_phase_already_changed() -> None:
    """phase가 이미 변경된 경우 액티브 타이머 콜백이 전환 skip."""
    fsm = _make_fsm(["seer"])
    fsm.state.phase = WerewolfPhase.DAY_DISCUSSION.value

    initial_version = fsm.state.state_version
    with patch("games.werewolf.fsm.ACTIVE_PHASE_TIMEOUT", 0):
        await fsm._run_active_timer(WerewolfPhase.NIGHT_SEER)

    assert fsm.state.phase == WerewolfPhase.DAY_DISCUSSION.value
    assert fsm.state.state_version == initial_version


@pytest.mark.anyio
async def test_active_timer_cancelled_on_new_phase_entry() -> None:
    """새 phase 진입 시 이전 액티브 타이머가 취소되고 _active_timer_task가 None으로 초기화됨."""
    fsm = _make_fsm(["seer"])

    with patch("games.werewolf.fsm.ACTIVE_PHASE_TIMEOUT", 60):
        fsm._enter_phase(WerewolfPhase.NIGHT_SEER)
        await asyncio.sleep(0)
        task = fsm._active_timer_task
        assert task is not None and not task.done()

        fsm._enter_phase(WerewolfPhase.DAY_DISCUSSION)
        await asyncio.sleep(0)

    # _run_active_timer가 CancelledError를 내부에서 catch하므로 task.cancelled()는 False.
    # cancel()이 전송되었음을 확인: task가 done 상태이고 fsm의 참조가 None으로 초기화됨.
    assert task.done()
    assert fsm._active_timer_task is None
