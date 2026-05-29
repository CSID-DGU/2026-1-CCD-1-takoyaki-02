"""한밤의 늑대인간 FSM 타이머 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from core.events import GameEvent
from games.werewolf.fsm import VOTE_COUNTDOWN_SECONDS, WerewolfFSM
from games.werewolf.ontology import WerewolfEventType, WerewolfInputType, WerewolfPhase
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


# ── 투표 카운트다운 & lock ────────────────────────────────────────────────────


def _set_vote_countdown_state(fsm: WerewolfFSM) -> None:
    """테스트용: VOTE_COUNTDOWN 상태를 직접 설정한다 (타이머 task 없이)."""
    fsm.state.phase = WerewolfPhase.VOTE_COUNTDOWN.value
    fsm.state.votes_locked = False
    fsm.state.countdown_remaining = VOTE_COUNTDOWN_SECONDS
    for p in fsm.state.players:
        p.voted_for = None
    fsm.state.state_version += 1


@pytest.mark.anyio
async def test_vote_countdown_enter_initializes_flags() -> None:
    """VOTE_COUNTDOWN 진입(_enter_phase) 시 votes_locked=False, countdown_remaining=초기값."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    fsm.state.phase = WerewolfPhase.DAY_DISCUSSION.value
    fsm._advance_to_next_phase()
    await asyncio.sleep(0)  # task 스케줄 양보

    assert fsm.state.phase == WerewolfPhase.VOTE_COUNTDOWN.value
    assert fsm.state.votes_locked is False
    assert fsm.state.countdown_remaining == VOTE_COUNTDOWN_SECONDS


@pytest.mark.anyio
async def test_vote_countdown_enter_clears_votes() -> None:
    """VOTE_COUNTDOWN 진입 시 모든 플레이어의 voted_for가 None으로 초기화된다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    for p in fsm.state.players:
        p.voted_for = "p_0"
    fsm.state.phase = WerewolfPhase.DAY_DISCUSSION.value
    fsm._advance_to_next_phase()
    await asyncio.sleep(0)

    assert all(p.voted_for is None for p in fsm.state.players)


def test_vision_vote_updates_voted_for_before_lock() -> None:
    """lock 전 비전 지목은 voted_for를 갱신하고 자동 전이하지 않는다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    _set_vote_countdown_state(fsm)

    event = GameEvent(
        event_type=WerewolfEventType.VOTE_POINT,
        actor_id="p_0",
        confidence=0.9,
        frame_id=1,
        data={"target_id": "p_1"},
    )
    msgs = fsm.handle_event(event)

    assert fsm.state.get_player("p_0").voted_for == "p_1"
    assert fsm.state.phase == WerewolfPhase.VOTE_COUNTDOWN.value
    assert any(True for _ in msgs)  # state_update 발송 확인


def test_vision_vote_allows_retarget() -> None:
    """lock 전 같은 투표자가 A→B로 재지목하면 voted_for가 갱신된다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    _set_vote_countdown_state(fsm)

    def _vote(actor, target):
        return fsm.handle_event(GameEvent(
            event_type=WerewolfEventType.VOTE_POINT,
            actor_id=actor, confidence=0.9, frame_id=1,
            data={"target_id": target},
        ))

    _vote("p_0", "p_1")
    assert fsm.state.get_player("p_0").voted_for == "p_1"

    _vote("p_0", "p_2")
    assert fsm.state.get_player("p_0").voted_for == "p_2"


def test_vision_vote_rejected_after_lock() -> None:
    """lock 후 비전 지목은 무시된다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    _set_vote_countdown_state(fsm)
    fsm.state.votes_locked = True

    event = GameEvent(
        event_type=WerewolfEventType.VOTE_POINT,
        actor_id="p_0", confidence=0.9, frame_id=1,
        data={"target_id": "p_1"},
    )
    msgs = fsm.handle_event(event)

    assert fsm.state.get_player("p_0").voted_for is None
    assert msgs == []


def test_manual_vote_allowed_after_lock() -> None:
    """lock 후에도 werewolf_vote_player(수동 보정)는 voted_for를 갱신한다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    _set_vote_countdown_state(fsm)
    fsm.state.votes_locked = True

    msgs = fsm.handle_input(WerewolfInputType.VOTE_PLAYER, {"target_id": "p_1"}, "p_0")

    assert fsm.state.get_player("p_0").voted_for == "p_1"
    assert msgs  # state_update 발송 확인


def test_vote_result_confirm_only_when_locked() -> None:
    """VOTE_RESULT_CONFIRM은 votes_locked=True 상태에서만 페이즈 전이를 일으킨다."""
    fsm = _make_fsm(["werewolf", "villager", "villager"])
    _set_vote_countdown_state(fsm)

    # lock 전 → 무시
    msgs = fsm.handle_input(WerewolfInputType.VOTE_RESULT_CONFIRM, {}, None)
    assert msgs == []
    assert fsm.state.phase == WerewolfPhase.VOTE_COUNTDOWN.value

    # lock 후 → 다음 페이즈로 전이
    fsm.state.votes_locked = True
    msgs = fsm.handle_input(WerewolfInputType.VOTE_RESULT_CONFIRM, {}, None)
    assert msgs
    assert fsm.state.phase != WerewolfPhase.VOTE_COUNTDOWN.value


@pytest.mark.anyio
async def test_countdown_timer_decrements_and_locks() -> None:
    """_run_vote_countdown 실행 시 countdown_remaining이 감소하고 최종적으로 lock된다."""
    fsm = _make_fsm(["werewolf", "villager"])

    with patch("games.werewolf.fsm.VOTE_COUNTDOWN_SECONDS", 2), \
         patch("games.werewolf.fsm.VOTE_LOCK_GRACE", 0):
        fsm.state.phase = WerewolfPhase.DAY_DISCUSSION.value
        fsm._advance_to_next_phase()
        # 카운트다운 완료 + grace 대기
        await asyncio.sleep(2.2)

    assert fsm.state.votes_locked is True
    assert fsm.state.countdown_remaining is None
