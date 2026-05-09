"""yacht_runner 라우팅 + FSM on_fusion_context 콜백 검증.

실제 LocalBridge를 사용해 비전 발화 → 활성 YachtSession 라우팅 흐름을 검증.
WebSocket은 FakeWebSocket으로 대체.

asyncio loop은 별도 스레드에서 돌려서 yacht_runner._route_event의
run_coroutine_threadsafe가 정상 동작하도록 한다.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest

from backend.server import YachtSession
from backend.yacht_runner import YachtRunner
from bridge.local_bridge import LocalBridge
from core.constants import CommonEventType, MsgType
from core.events import FusionContext, GameEvent
from games.yacht import YachtEventType, YachtFSM

# ── FakeWebSocket ───────────────────────────────────────────────────────────


class FakeWebSocket:
    """WebSocket 인터페이스 중 send_json만 구현. 송신 메시지 기록."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def _make_event(event_type: str, actor_id: str = "p1", **data: Any) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        actor_id=actor_id,
        confidence=0.95,
        frame_id=1,
        data=data,
    )


@pytest.fixture()
def loop_in_thread():
    """asyncio loop을 별도 스레드에서 돌리는 fixture."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=1.0)
    loop.close()


def _start_session_sync(session: YachtSession, loop: asyncio.AbstractEventLoop) -> None:
    """async start_game을 동기로 실행 (해당 loop에서)."""
    fut = asyncio.run_coroutine_threadsafe(
        session.start_game({"players": [{"player_id": "p1", "playername": "A"}]}),
        loop,
    )
    fut.result(timeout=2.0)


# ── YachtRunner 라우팅 ──────────────────────────────────────────────────────


def test_yacht_event_routes_to_active_session(loop_in_thread) -> None:
    """ROLL_CONFIRMED 발화 → 활성 session.dispatch_vision_event 호출."""
    bridge = LocalBridge()
    runner = YachtRunner(bridge=bridge, loop=loop_in_thread)

    ws = FakeWebSocket()
    session = YachtSession(websocket=ws, bridge=bridge)
    _start_session_sync(session, loop_in_thread)
    runner.register_session(session)

    sent_before = len(ws.sent)

    event = _make_event(
        YachtEventType.ROLL_CONFIRMED.value,
        dice_values=[1, 2, 3, 4, 5],
        keep_mask=[False] * 5,
    )
    bridge.send_game_event(event, state_version=2)

    # asyncio loop이 schedule된 task를 처리할 시간 확보
    time.sleep(0.1)

    # FSM이 ROLL_CONFIRMED를 받아 응답 메시지 발화
    new_msgs = ws.sent[sent_before:]
    sent_msg_types = [m.get("msg_type") for m in new_msgs]
    assert MsgType.STATE_UPDATE.value in sent_msg_types, f"got {sent_msg_types}"
    assert MsgType.FUSION_CONTEXT.value in sent_msg_types


def test_yacht_event_ignored_when_no_active_session(loop_in_thread) -> None:
    """활성 세션 없을 때 ROLL_CONFIRMED 도착 → 예외 없이 무시."""
    bridge = LocalBridge()
    YachtRunner(bridge=bridge, loop=loop_in_thread)  # register 안 함

    event = _make_event(YachtEventType.ROLL_CONFIRMED.value, dice_values=[1] * 5)
    bridge.send_game_event(event, state_version=1)
    time.sleep(0.05)
    # 예외만 안 뜨면 OK


def test_non_yacht_event_not_routed_to_yacht(loop_in_thread) -> None:
    """SEAT_REGISTERED 같은 비-yacht 이벤트는 yacht runner가 무시해야 함."""
    bridge = LocalBridge()
    runner = YachtRunner(bridge=bridge, loop=loop_in_thread)

    ws = FakeWebSocket()
    session = YachtSession(websocket=ws, bridge=bridge)
    _start_session_sync(session, loop_in_thread)
    runner.register_session(session)

    sent_before = len(ws.sent)
    event = _make_event(CommonEventType.SEAT_REGISTERED.value)
    bridge.send_game_event(event, state_version=1)
    time.sleep(0.05)

    # FSM은 SEAT_REGISTERED 안 받으므로 추가 메시지 없음
    assert len(ws.sent) == sent_before


# ── FSM on_fusion_context 콜백 ──────────────────────────────────────────────


def test_fusion_context_published_on_start() -> None:
    """FSM.start() 호출 시 on_fusion_context 콜백 호출."""
    received: list[tuple[FusionContext, int]] = []

    fsm = YachtFSM(
        [{"player_id": "p1", "playername": "A"}],
        on_fusion_context=lambda ctx, ver: received.append((ctx, ver)),
    )
    messages = fsm.start()

    assert len(received) == 1
    ctx, ver = received[0]
    assert ctx.game_type == "yacht"
    assert ctx.fsm_state == "AWAITING_ROLL"
    assert ver == fsm.state.state_version
    assert any(m.msg_type == MsgType.FUSION_CONTEXT.value for m in messages)


def test_fusion_context_published_after_roll_confirmed() -> None:
    """ROLL_CONFIRMED 처리 후 두 번째 on_fusion_context 호출 (AWAITING_KEEP)."""
    received: list[tuple[FusionContext, int]] = []

    fsm = YachtFSM(
        [{"player_id": "p1", "playername": "A"}],
        on_fusion_context=lambda ctx, ver: received.append((ctx, ver)),
    )
    fsm.start()

    event = _make_event(
        YachtEventType.ROLL_CONFIRMED.value,
        dice_values=[1, 2, 3, 4, 5],
        keep_mask=[False] * 5,
    )
    fsm.handle_event(event)

    assert len(received) >= 2
    last_ctx, _ = received[-1]
    assert last_ctx.fsm_state in ("AWAITING_KEEP", "AWAITING_SCORE")


def test_fsm_works_without_on_fusion_context_callback() -> None:
    """콜백 미주입 환경에서도 FSM은 정상 동작 (단위 테스트 호환성)."""
    fsm = YachtFSM([{"player_id": "p1", "playername": "A"}])
    messages = fsm.start()
    assert any(m.msg_type == MsgType.FUSION_CONTEXT.value for m in messages)


# ── deregister race condition ───────────────────────────────────────────────


def test_deregister_only_clears_matching_session(loop_in_thread) -> None:
    """빠른 재연결 시 새 세션을 옛 세션의 deregister가 덮어쓰지 않아야."""
    bridge = LocalBridge()
    runner = YachtRunner(bridge=bridge, loop=loop_in_thread)

    ws = FakeWebSocket()
    old_session = YachtSession(websocket=ws, bridge=bridge)
    new_session = YachtSession(websocket=ws, bridge=bridge)

    runner.register_session(old_session)
    runner.register_session(new_session)
    runner.deregister_session(old_session)

    assert runner._active_session is new_session
