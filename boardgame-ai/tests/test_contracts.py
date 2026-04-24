"""core/ 타입 직렬화·구조 유지 계약 테스트.

core/ 타입만 검증. vision/games 코드 import 없음.
JSON 라운드트립 중심으로 팀원이 core/ 수정 시 계약 깨지면 즉시 감지.
"""

import json

import pytest

from core.audio import AudioPriority, AudioType, TTSRequest
from core.constants import CommonEventType, CommonPhase
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from core.models import Player, SeatZone
from core.player_manager import PlayerManager

# ---------------------------------------------------------------------------
# SeatZone
# ---------------------------------------------------------------------------


def test_seat_zone_roundtrip():
    sz = SeatZone(right_hand_wrist=(0.3, 0.4), left_hand_wrist=(0.6, 0.7))
    restored = SeatZone.from_dict(json.loads(json.dumps(sz.to_dict())))
    assert restored.right_hand_wrist == pytest.approx((0.3, 0.4))
    assert restored.left_hand_wrist == pytest.approx((0.6, 0.7))


def test_seat_zone_wrists_in_unit_range():
    sz = SeatZone(right_hand_wrist=(0.0, 1.0), left_hand_wrist=(0.5, 0.5))
    for coord in [*sz.right_hand_wrist, *sz.left_hand_wrist]:
        assert 0.0 <= coord <= 1.0


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


def test_player_roundtrip_with_seat_zone():
    sz = SeatZone(right_hand_wrist=(0.1, 0.2), left_hand_wrist=(0.8, 0.9))
    p = Player(player_id="p_abc", playername="Alice", seat_zone=sz, registered_at=1000.0)
    restored = Player.from_dict(json.loads(json.dumps(p.to_dict())))
    assert restored.player_id == "p_abc"
    assert restored.playername == "Alice"
    assert restored.seat_zone is not None
    assert restored.seat_zone.right_hand_wrist == pytest.approx((0.1, 0.2))
    assert restored.registered_at == pytest.approx(1000.0)


def test_player_roundtrip_without_seat_zone():
    p = Player(player_id="p_xyz", playername="Bob")
    restored = Player.from_dict(json.loads(json.dumps(p.to_dict())))
    assert restored.player_id == "p_xyz"
    assert restored.seat_zone is None


# ---------------------------------------------------------------------------
# GameEvent
# ---------------------------------------------------------------------------


def test_game_event_roundtrip():
    ev = GameEvent(
        event_type=CommonEventType.GESTURE_CONFIRMED.value,
        actor_id="p_001",
        confidence=0.95,
        frame_id=42,
        data={"gesture": "v_sign"},
    )
    restored = GameEvent.from_dict(json.loads(json.dumps(ev.to_dict())))
    assert restored.event_type == CommonEventType.GESTURE_CONFIRMED.value
    assert restored.actor_id == "p_001"
    assert restored.confidence == pytest.approx(0.95)
    assert restored.frame_id == 42
    assert restored.data == {"gesture": "v_sign"}


def test_game_event_accepts_arbitrary_event_type_string():
    """게임별 event_type 문자열을 core가 거부하지 않음을 확인."""
    ev = GameEvent(
        event_type="yacht_dice_stable",
        actor_id="p_002",
        confidence=0.8,
        frame_id=10,
        data={"dice": [1, 2, 3, 4, 5]},
    )
    restored = GameEvent.from_dict(json.loads(json.dumps(ev.to_dict())))
    assert restored.event_type == "yacht_dice_stable"


def test_game_event_roundtrip_with_none_actor():
    ev = GameEvent(
        event_type=CommonEventType.VISION_ERROR.value,
        actor_id=None,
        confidence=0.0,
        frame_id=0,
        data={"error_code": "E001", "message": "no frame"},
    )
    restored = GameEvent.from_dict(json.loads(json.dumps(ev.to_dict())))
    assert restored.actor_id is None


# ---------------------------------------------------------------------------
# FusionContext
# ---------------------------------------------------------------------------


def test_fusion_context_roundtrip():
    ctx = FusionContext(
        fsm_state=CommonPhase.PLAYER_SETUP.value,
        game_type=None,
        active_player="p_001",
        allowed_actors=["p_001", "p_002"],
        expected_events=[CommonEventType.SEAT_HAND_REGISTERED.value],
        reject_events=[CommonEventType.RULE_VIOLATION.value],
        params={"confidence_threshold": 0.6},
    )
    restored = FusionContext.from_dict(json.loads(json.dumps(ctx.to_dict())))
    assert restored.fsm_state == CommonPhase.PLAYER_SETUP.value
    assert restored.game_type is None
    assert restored.active_player == "p_001"
    assert CommonEventType.SEAT_HAND_REGISTERED.value in restored.expected_events
    assert restored.params["confidence_threshold"] == pytest.approx(0.6)


def test_fusion_context_expects_reject_overrides():
    ctx = FusionContext(
        fsm_state="some_state",
        game_type="yacht",
        active_player=None,
        allowed_actors=[],
        expected_events=["evt_a", "evt_b"],
        reject_events=["evt_a"],
    )
    assert not ctx.expects("evt_a"), "reject_events should override expected_events"
    assert ctx.expects("evt_b")
    assert not ctx.expects("evt_c")


def test_fusion_context_is_actor_allowed():
    ctx = FusionContext(
        fsm_state="some_state",
        game_type=None,
        active_player=None,
        allowed_actors=["p_001"],
        expected_events=[],
    )
    assert ctx.is_actor_allowed("p_001")
    assert not ctx.is_actor_allowed("p_002")


# ---------------------------------------------------------------------------
# WSMessage
# ---------------------------------------------------------------------------


def test_ws_message_roundtrip():
    msg = WSMessage(msg_type="game_event", payload={"key": "val"}, state_version=3)
    restored = WSMessage.from_dict(json.loads(json.dumps(msg.to_dict())))
    assert restored.msg_type == "game_event"
    assert restored.payload == {"key": "val"}
    assert restored.state_version == 3


def test_ws_message_envelope_fields():
    msg = WSMessage(msg_type="hello", payload={})
    d = msg.to_dict()
    for field in ("msg_type", "msg_id", "timestamp", "state_version", "payload"):
        assert field in d, f"Missing field: {field}"
    assert isinstance(d["msg_id"], str)
    assert isinstance(d["timestamp"], float)


# ---------------------------------------------------------------------------
# TTSRequest
# ---------------------------------------------------------------------------


def test_tts_request_roundtrip():
    req = TTSRequest(
        text="주사위를 굴려주세요",
        audio_url="/cache/roll.wav",
        audio_type=AudioType.TTS,
        priority=AudioPriority.HIGH,
        agent="narrator",
        interruptible=False,
        playback_id="pb_001",
        state_version=5,
    )
    restored = TTSRequest.from_dict(json.loads(json.dumps(req.to_dict())))
    assert restored.text == "주사위를 굴려주세요"
    assert restored.audio_url == "/cache/roll.wav"
    assert restored.audio_type == AudioType.TTS
    assert restored.priority == AudioPriority.HIGH
    assert restored.interruptible is False
    assert restored.playback_id == "pb_001"
    assert restored.state_version == 5


# ---------------------------------------------------------------------------
# PlayerManager
# ---------------------------------------------------------------------------


def test_player_manager_add_and_list():
    pm = PlayerManager()
    pid = pm.add_player("Alice")
    assert isinstance(pid, str)
    # seat_zone=None이면 get_players()가 ValueError
    with pytest.raises(ValueError):
        pm.get_players()
    # 플레이어 목록에는 포함됨
    assert any(p.player_id == pid for p in pm.state.players)
    assert pm.state.players[0].seat_zone is None


def test_player_manager_seat_registration_flow():
    pm = PlayerManager()
    pid = pm.add_player("Bob")

    pm.start_seat_registration(pid)
    done = pm.record_hand("Right", (0.3, 0.4))
    assert not done, "양손 모두 기록해야 True"

    done = pm.record_hand("Left", (0.7, 0.6))
    assert done, "양손 기록 완료 시 True"

    player = pm.finalize_seat()
    assert player.seat_zone is not None
    assert player.seat_zone.right_hand_wrist == pytest.approx((0.3, 0.4))
    assert player.seat_zone.left_hand_wrist == pytest.approx((0.7, 0.6))

    # 이제 get_players() 정상 반환
    players = pm.get_players()
    assert len(players) == 1
    assert players[0].player_id == pid


def test_player_manager_remove_preserves_others():
    pm = PlayerManager()
    pid_a = pm.add_player("Alice")
    pid_b = pm.add_player("Bob")
    pm.remove_player(pid_a)
    remaining = [p.player_id for p in pm.state.players]
    assert pid_a not in remaining
    assert pid_b in remaining
