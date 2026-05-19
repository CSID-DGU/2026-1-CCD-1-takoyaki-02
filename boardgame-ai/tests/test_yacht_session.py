from __future__ import annotations

import pytest

from backend.server import YachtSession
from core.events import GameEvent
from games.yacht import YachtEventType


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


def _latest_state(ws: FakeWebSocket) -> dict:
    return [msg for msg in ws.sent if msg["msg_type"] == "state_update"][-1]["payload"]


@pytest.mark.anyio
async def test_yacht_session_undo_restores_last_dice_roll_only():
    ws = FakeWebSocket()
    session = YachtSession(ws)

    await session.start_game(
        {
            "players": [
                {"player_id": "p1", "playername": "p1"},
                {"player_id": "p2", "playername": "p2"},
            ]
        }
    )
    await session.handle_client_message(
        {"input_type": "ROLL_DICE", "data": {"dice_values": [1, 1, 3, 4, 6]}}
    )

    rolled = _latest_state(ws)
    assert rolled["roll_count"] == 1
    assert rolled["dice_values"] == [1, 1, 3, 4, 6]
    assert rolled["can_undo"] is True

    await session.handle_client_message({"input_type": "UNDO_ROUND", "data": {}})

    undone = _latest_state(ws)
    assert undone["current_player_id"] == "p1"
    assert undone["roll_count"] == 0
    assert undone["dice_values"] == []
    assert undone["phase"] == "AWAITING_ROLL"
    assert undone["can_undo"] is False


@pytest.mark.anyio
async def test_yacht_session_score_selection_clears_dice_undo_history():
    ws = FakeWebSocket()
    session = YachtSession(ws)

    await session.start_game(
        {
            "players": [
                {"player_id": "p1", "playername": "p1"},
                {"player_id": "p2", "playername": "p2"},
            ]
        }
    )
    await session.handle_client_message(
        {"input_type": "ROLL_DICE", "data": {"dice_values": [1, 1, 3, 4, 6]}}
    )
    await session.handle_client_message(
        {
            "input_type": "SCORE_CATEGORY_SELECTED",
            "player_id": "p1",
            "data": {"category": "ones"},
        }
    )

    scored = _latest_state(ws)
    assert scored["current_player_id"] == "p2"
    assert scored["players"][0]["scores"] == {"ones": 2}
    assert scored["can_undo"] is False


@pytest.mark.anyio
async def test_yacht_tutorial_mode_accepts_vision_rolls():
    ws = FakeWebSocket()
    session = YachtSession(ws)

    await session.start_game(
        {
            "tutorial_mode": True,
            "players": [{"player_id": "p1", "playername": "p1"}],
        }
    )

    started = _latest_state(ws)
    assert started["tutorial_mode"] is True

    await session.dispatch_vision_event(
        GameEvent(
            event_type=YachtEventType.ROLL_CONFIRMED.value,
            actor_id="p1",
            confidence=0.95,
            frame_id=10,
            data={"dice_values": [1, 2, 3, 4, 5], "keep_mask": [False] * 5},
        )
    )

    after_vision = _latest_state(ws)
    assert after_vision["roll_count"] == 1
    assert after_vision["dice_values"] == [1, 2, 3, 4, 5]
    assert after_vision["tutorial_mode"] is True


@pytest.mark.anyio
async def test_yacht_tutorial_mode_finishes_after_each_player_scores_once():
    ws = FakeWebSocket()
    session = YachtSession(ws)

    await session.start_game(
        {
            "tutorial_mode": True,
            "players": [
                {"player_id": "p1", "playername": "p1"},
                {"player_id": "p2", "playername": "p2"},
            ],
        }
    )

    await session.handle_client_message(
        {"input_type": "ROLL_DICE", "data": {"dice_values": [1, 1, 3, 4, 6]}}
    )
    await session.handle_client_message(
        {
            "input_type": "SCORE_CATEGORY_SELECTED",
            "player_id": "p1",
            "data": {"category": "ones"},
        }
    )

    after_p1 = _latest_state(ws)
    assert after_p1["tutorial_complete"] is False
    assert after_p1["current_player_id"] == "p2"

    await session.handle_client_message(
        {"input_type": "ROLL_DICE", "data": {"dice_values": [2, 2, 3, 4, 6]}}
    )
    await session.handle_client_message(
        {
            "input_type": "SCORE_CATEGORY_SELECTED",
            "player_id": "p2",
            "data": {"category": "twos"},
        }
    )

    completed = _latest_state(ws)
    assert completed["tutorial_complete"] is True
    assert completed["players"][0]["scores"] == {"ones": 2}
    assert completed["players"][1]["scores"] == {"twos": 4}

