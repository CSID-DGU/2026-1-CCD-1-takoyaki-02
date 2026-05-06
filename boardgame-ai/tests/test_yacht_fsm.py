from core.constants import MsgType
from core.events import GameEvent
from games.yacht import YachtEventType, YachtFSM, YachtInputType, YachtPhase


def _event(event_type: str, actor_id: str = "p1", dice=None) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        actor_id=actor_id,
        confidence=0.95,
        frame_id=1,
        data={"dice_values": dice or [1, 2, 3, 4, 5], "keep_mask": [False] * 5},
    )


def _messages_of(msgs, msg_type):
    return [msg for msg in msgs if msg.msg_type == msg_type]


def test_start_sends_roll_context_for_first_player():
    fsm = YachtFSM(["p1", "p2"])

    msgs = fsm.start()
    ctx = _messages_of(msgs, MsgType.FUSION_CONTEXT.value)[0].payload

    assert fsm.state.phase == YachtPhase.AWAITING_ROLL.value
    assert ctx["fsm_state"] == YachtPhase.AWAITING_ROLL.value
    assert ctx["active_player"] == "p1"
    assert ctx["allowed_actors"] == ["p1"]
    assert YachtEventType.ROLL_CONFIRMED.value in ctx["expected_events"]
    assert YachtEventType.ROLL_UNREADABLE.value in ctx["expected_events"]


def test_roll_confirmed_moves_to_keep_before_third_roll():
    fsm = YachtFSM(["p1"])
    fsm.start()

    msgs = fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value))

    assert fsm.state.roll_count == 1
    assert fsm.state.dice_values == [1, 2, 3, 4, 5]
    assert fsm.state.phase == YachtPhase.AWAITING_KEEP.value
    assert _messages_of(msgs, MsgType.STATE_UPDATE.value)


def test_reroll_returns_to_awaiting_roll_with_same_player():
    fsm = YachtFSM(["p1", "p2"])
    fsm.start()
    fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value))

    msgs = fsm.handle_input(
        YachtInputType.DICE_REROLL_REQUESTED.value,
        {"keep_mask": [True, False, False, False, True]},
        player_id="p1",
    )
    ctx = _messages_of(msgs, MsgType.FUSION_CONTEXT.value)[0].payload

    assert fsm.state.phase == YachtPhase.AWAITING_ROLL.value
    assert fsm.state.keep_mask == [True, False, False, False, True]
    assert ctx["active_player"] == "p1"


def test_third_roll_forces_score_phase():
    fsm = YachtFSM(["p1"])
    fsm.start()

    for _ in range(2):
        fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value))
        fsm.handle_input(YachtInputType.DICE_REROLL_REQUESTED.value, {}, player_id="p1")
    fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value))

    assert fsm.state.roll_count == 3
    assert fsm.state.phase == YachtPhase.AWAITING_SCORE.value


def test_score_selection_records_score_and_advances_player():
    fsm = YachtFSM(["p1", "p2"])
    fsm.start()
    fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value, dice=[1, 1, 3, 4, 6]))

    msgs = fsm.handle_input(
        YachtInputType.SCORE_CATEGORY_SELECTED.value,
        {"category": "ones"},
        player_id="p1",
    )

    assert fsm.state.players[0].scores["ones"] == 2
    assert fsm.state.current_player.player_id == "p2"
    assert fsm.state.phase == YachtPhase.AWAITING_ROLL.value
    assert _messages_of(msgs, MsgType.FUSION_CONTEXT.value)[0].payload["active_player"] == "p2"


def test_unreadable_roll_waits_for_manual_resolution():
    fsm = YachtFSM(["p1"])
    fsm.start()

    fsm.handle_event(
        GameEvent(
            event_type=YachtEventType.ROLL_UNREADABLE.value,
            actor_id="p1",
            confidence=0.6,
            frame_id=1,
            data={"dice_values": [1, None, 3, 4, None], "unknown_indices": [1, 4]},
        )
    )

    assert fsm.state.phase == YachtPhase.AWAITING_SCORE.value
    assert fsm.state.unreadable_roll["unknown_indices"] == [1, 4]


def test_wrong_turn_does_not_count_roll():
    fsm = YachtFSM(["p1", "p2"])
    fsm.start()

    fsm.handle_event(_event(YachtEventType.ROLL_CONFIRMED.value, actor_id="p2"))

    assert fsm.state.roll_count == 0
    assert fsm.state.phase == YachtPhase.AWAITING_ROLL.value
