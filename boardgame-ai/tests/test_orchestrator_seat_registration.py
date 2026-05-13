from __future__ import annotations

from backend.orchestrator import Orchestrator
from core.constants import CommonPhase


def _orch() -> Orchestrator:
    return Orchestrator(send_fusion_context_fn=lambda _ctx, _version: None)


def test_cancel_seat_registration_clears_pending_temp_player() -> None:
    orchestrator = _orch()
    result = orchestrator.start_registration()

    orchestrator.cancel_seat_registration(result["player_id"])
    snapshot = orchestrator.current_snapshot()

    assert snapshot["phase"] == CommonPhase.PLAYER_SETUP
    assert snapshot["registering_player_id"] is None
    assert snapshot["seat_step"] == "idle"
    assert snapshot["players"] == []


def test_remove_registering_player_clears_registration_state() -> None:
    orchestrator = _orch()
    result = orchestrator.start_registration()

    orchestrator.remove_player(result["player_id"])
    snapshot = orchestrator.current_snapshot()

    assert snapshot["phase"] == CommonPhase.PLAYER_SETUP
    assert snapshot["registering_player_id"] is None
    assert snapshot["seat_step"] == "idle"
    assert snapshot["players"] == []

