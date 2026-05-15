"""오디오 시스템 단위 테스트.

AudioManager의 우선순위 큐 / CRITICAL 인터럽트 / ack-driven 푸시 /
sequence 직렬화 / non-interruptible 보호 동작을 검증한다.

Google API는 호출하지 않는다. TTSEngine.synthesize / cache_hit을 mock하여
디스크 IO 없이 빠르게 검증.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio  # noqa: F401  (마커 활성화)

from audio.manager import AudioManager
from audio.tts_engine import TTSEngine
from core.audio import AudioPriority
from core.envelope import WSMessage


@pytest.fixture
def mock_engine() -> TTSEngine:
    """캐시 hit으로 즉시 fake Path를 반환하는 mock engine."""
    engine = MagicMock(spec=TTSEngine)
    engine.cache_hit = MagicMock(return_value=Path("/cache/tts/static/fake.wav"))
    engine.synthesize = AsyncMock(return_value=Path("/cache/tts/static/fake.wav"))
    engine.is_available = MagicMock(return_value=True)
    return engine


@pytest.fixture
def manager_and_sent(mock_engine: TTSEngine) -> tuple[AudioManager, list[WSMessage]]:
    mgr = AudioManager(mock_engine)
    sent: list[WSMessage] = []

    async def cb(m: WSMessage) -> None:
        sent.append(m)

    mgr.attach_broadcast(cb)
    return mgr, sent


@pytest.mark.asyncio
async def test_ack_driven_push(manager_and_sent: tuple[AudioManager, list[WSMessage]]) -> None:
    """ack 받기 전엔 두 번째 항목이 broadcast되지 않는다."""
    mgr, sent = manager_and_sent
    pb1 = await mgr.enqueue_tts("첫번째 멘트입니다.")
    pb2 = await mgr.enqueue_tts("두번째 멘트입니다.")
    assert len(sent) == 1
    assert sent[0].payload["playback_id"] == pb1
    assert len(mgr._queue) == 1

    await mgr.handle_ack(pb1, "played")
    assert len(sent) == 2
    assert sent[1].payload["playback_id"] == pb2


@pytest.mark.asyncio
async def test_priority_ordering(manager_and_sent: tuple[AudioManager, list[WSMessage]]) -> None:
    """HIGH가 LOW보다 먼저 dequeue된다."""
    mgr, sent = manager_and_sent
    pb_n = await mgr.enqueue_tts("일반 멘트입니다.", priority=AudioPriority.NORMAL)
    pb_low = await mgr.enqueue_tts("로우 멘트입니다.", priority=AudioPriority.LOW)
    pb_high = await mgr.enqueue_tts("하이 멘트입니다.", priority=AudioPriority.HIGH)

    assert sent[0].payload["playback_id"] == pb_n
    await mgr.handle_ack(pb_n, "played")
    assert sent[1].payload["playback_id"] == pb_high
    await mgr.handle_ack(pb_high, "played")
    assert sent[2].payload["playback_id"] == pb_low


@pytest.mark.asyncio
async def test_critical_interrupts_current(
    manager_and_sent: tuple[AudioManager, list[WSMessage]],
) -> None:
    """CRITICAL 도착 시 진행 중인 interruptible 항목에 tts_interrupt 발행."""
    mgr, sent = manager_and_sent
    pb_n = await mgr.enqueue_tts("일반 진행 멘트입니다.", priority=AudioPriority.NORMAL)
    pb_low = await mgr.enqueue_tts("대기 중인 로우입니다.", priority=AudioPriority.LOW)

    pb_c = await mgr.enqueue_tts("긴급 멘트입니다!", priority=AudioPriority.CRITICAL)

    interrupts = [m for m in sent if m.msg_type == "tts_interrupt"]
    assert len(interrupts) == 1
    assert interrupts[0].payload["playback_id"] == pb_n
    # interruptible LOW는 큐에서 제거되어야
    assert all(q.playback_id != pb_low for q in mgr._queue)
    # CRITICAL이 새 _current
    assert mgr._current is not None and mgr._current.playback_id == pb_c


@pytest.mark.asyncio
async def test_critical_does_not_drop_non_interruptible(
    manager_and_sent: tuple[AudioManager, list[WSMessage]],
) -> None:
    """interruptible=False 항목은 CRITICAL이 와도 큐에 남는다."""
    mgr, sent = manager_and_sent
    await mgr.enqueue_tts("일반 멘트입니다.", priority=AudioPriority.NORMAL)
    pb_protected = await mgr.enqueue_tts(
        "보호된 멘트입니다.", priority=AudioPriority.NORMAL, interruptible=False
    )
    await mgr.enqueue_tts("긴급입니다!", priority=AudioPriority.CRITICAL)

    queue_or_current = [q.playback_id for q in mgr._queue] + (
        [mgr._current.playback_id] if mgr._current else []
    )
    assert pb_protected in queue_or_current


@pytest.mark.asyncio
async def test_sequence_serialization(
    manager_and_sent: tuple[AudioManager, list[WSMessage]],
) -> None:
    """같은 sequence_id 내 항목은 seq_index 순서대로 dequeue된다."""
    mgr, sent = manager_and_sent
    sid = "seq_test"
    pb1 = await mgr.enqueue_tts("순서 1 멘트입니다.", sequence_id=sid, seq_index=0)
    pb3 = await mgr.enqueue_tts("순서 3 멘트입니다.", sequence_id=sid, seq_index=2)
    pb2 = await mgr.enqueue_tts("순서 2 멘트입니다.", sequence_id=sid, seq_index=1)

    assert sent[0].payload["playback_id"] == pb1
    await mgr.handle_ack(pb1, "played")
    assert sent[1].payload["playback_id"] == pb2
    await mgr.handle_ack(pb2, "played")
    assert sent[2].payload["playback_id"] == pb3


@pytest.mark.asyncio
async def test_handle_ack_idempotent_on_unknown_id(
    manager_and_sent: tuple[AudioManager, list[WSMessage]],
) -> None:
    """모르는 playback_id 대한 ack는 무시되어야 하며 큐 진행만 트리거."""
    mgr, sent = manager_and_sent
    pb1 = await mgr.enqueue_tts("멘트입니다.")
    # 이미 _current가 pb1
    assert mgr._current is not None and mgr._current.playback_id == pb1
    # 모르는 id로 ack — 무시. _current 그대로.
    await mgr.handle_ack("pb_unknown", "played")
    assert mgr._current is not None and mgr._current.playback_id == pb1
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_synthesis_failure_text_only(mock_engine: Any) -> None:
    """합성 실패 시에도 broadcast는 일어남(audio_url=None). 큐 진행 가능."""
    mock_engine.cache_hit = MagicMock(return_value=None)
    mock_engine.synthesize = AsyncMock(return_value=None)
    mgr = AudioManager(mock_engine)
    sent: list[WSMessage] = []

    async def cb(m: WSMessage) -> None:
        sent.append(m)

    mgr.attach_broadcast(cb)
    pb = await mgr.enqueue_tts("합성 실패하는 멘트입니다.")
    assert len(sent) == 1
    assert sent[0].payload["audio_url"] is None
    assert sent[0].payload["playback_id"] == pb


@pytest.mark.asyncio
async def test_llm_entry_point_uses_same_queue(
    manager_and_sent: tuple[AudioManager, list[WSMessage]],
) -> None:
    """enqueue_llm_line은 enqueue_tts와 동일한 큐를 공유."""
    mgr, sent = manager_and_sent
    pb1 = await mgr.enqueue_tts("일반 멘트입니다.")
    pb2 = await mgr.enqueue_llm_line(
        agent="narrator", text="LLM이 생성한 멘트입니다.", priority=AudioPriority.NORMAL
    )
    assert len(sent) == 1  # pb1만
    await mgr.handle_ack(pb1, "played")
    assert len(sent) == 2
    assert sent[1].payload["playback_id"] == pb2
