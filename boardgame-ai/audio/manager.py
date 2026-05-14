"""AudioManager — FSM의 오디오 메시지를 가로채 합성/캐시 후 frontend로 broadcast.

M1 범위(현재):
- FIFO 큐 (우선순위는 M2에서 추가).
- tts_play 메시지 수신 → 캐시 hit이면 audio_url 채워 즉시 broadcast.
- 캐시 miss면 비동기 합성 후 broadcast.
- sfx_play / bgm_play / bgm_duck pass-through.
- audio_ack 수신 → 큐 진행(현재는 fire-and-forget이라 큐 동시 처리 가능).
- playback_id 자동 부여.
- enqueue_llm_line(): 승경팀 LLM 멘트 진입점.
- prewarm_session_async(): 좌석 등록 hook용 fire-and-forget.

M2에서 추가될 것: 우선순위 deque, CRITICAL 인터럽트, sequence 직렬화, ducking 자동 발행.

스레드 모델:
- asyncio 단일 이벤트 루프 가정.
- broadcast 콜백은 활성 세션이 attach_broadcast()로 갈아끼움.
- 동시에 1개 게임만 진행되므로 매니저는 전역 1개.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from audio.catalog import (
    DEFAULT_VOICE,
    EXCITED_LINES,
    EXCITED_VOICE,
    VOICE_BY_AGENT,
    VoiceConfig,
    classify_text,
)
from audio.prewarm import make_session_id, prewarm_session, wipe_session
from audio.tts_engine import CacheLayer, TTSEngine
from core.audio import AudioPriority, SFXRequest, TTSRequest
from core.constants import MsgType
from core.envelope import WSMessage

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[WSMessage], Awaitable[None]]


def _new_playback_id() -> str:
    return f"pb_{uuid.uuid4().hex[:10]}"


class AudioManager:
    """오디오 출력 단일 진입점.

    사용:
        mgr = AudioManager(engine)
        mgr.attach_broadcast(session.send)   # 세션 전환마다 갈아끼움
        # FSM이 만든 tts_play WSMessage를 세션이 받으면:
        if msg.msg_type == MsgType.TTS_PLAY:
            await mgr.handle_outbound(msg)
        else:
            await session.send_raw(msg)
    """

    def __init__(self, engine: TTSEngine) -> None:
        self._engine = engine
        self._broadcast: BroadcastFn | None = None
        self._active_session_id: str | None = None

    # ── 세션 라이프사이클 ──────────────────────────────────────────────────────

    def attach_broadcast(
        self, broadcast: BroadcastFn, session_id: str | None = None
    ) -> None:
        """활성 세션의 broadcast 함수 연결. None이면 detach."""
        self._broadcast = broadcast
        self._active_session_id = session_id
        logger.info(
            "AudioManager broadcast attached (session_id=%s)", session_id
        )

    def detach_broadcast(self) -> None:
        self._broadcast = None
        self._active_session_id = None

    def get_session_id(self) -> str | None:
        return self._active_session_id

    # ── prewarm 헬퍼 ──────────────────────────────────────────────────────────

    def prewarm_session_async(self, player_names: list[str]) -> str:
        """좌석 등록 완료 후 fire-and-forget으로 session 캐시 준비.

        Returns: session_id (캐시 디렉토리에 사용).
        """
        session_id = make_session_id(player_names)
        self._active_session_id = session_id

        async def _run() -> None:
            try:
                await prewarm_session(self._engine, session_id, player_names)
            except Exception:
                logger.exception("prewarm_session_async failed (%s)", session_id)

        asyncio.create_task(_run())
        logger.info("prewarm_session_async scheduled (session_id=%s, players=%s)",
                    session_id, player_names)
        return session_id

    def wipe_session_cache(self, session_id: str) -> None:
        wipe_session(session_id)
        if self._active_session_id == session_id:
            self._active_session_id = None

    # ── outbound: FSM → AudioManager → frontend ───────────────────────────────

    async def handle_outbound(self, msg: WSMessage) -> None:
        """세션이 받은 audio 관련 WSMessage를 라우팅.

        - tts_play: 캐시/합성 → audio_url 채워 broadcast.
        - sfx_play, bgm_play, bgm_duck, tts_interrupt: 그대로 broadcast (현재).
        - 그 외: 호출하지 말 것.
        """
        if msg.msg_type == MsgType.TTS_PLAY.value:
            await self._handle_tts_play(msg)
        elif msg.msg_type in (
            MsgType.SFX_PLAY.value,
            MsgType.BGM_PLAY.value,
            MsgType.BGM_DUCK.value,
            MsgType.TTS_INTERRUPT.value,
        ):
            await self._send(msg)
        else:
            logger.warning(
                "AudioManager.handle_outbound: unexpected msg_type=%s", msg.msg_type
            )

    async def _handle_tts_play(self, msg: WSMessage) -> None:
        """tts_play 메시지의 text를 합성/캐시 후 audio_url 채워 broadcast."""
        request = TTSRequest.from_dict(msg.payload)
        if not request.playback_id:
            request.playback_id = _new_playback_id()

        voice = self._voice_for(request)
        layer, layer_session_id = self._layer_for(request.text)
        path = self._engine.cache_hit(request.text, voice, layer, session_id=layer_session_id)

        if path is None:
            # 합성을 await — M1은 단순 직렬. M2에서 다른 항목과 병렬화.
            path = await self._engine.synthesize(
                request.text, voice, layer, session_id=layer_session_id
            )

        if path is not None:
            request.audio_url = self._audio_url_for(path, layer, layer_session_id)
        else:
            logger.warning(
                "tts: synthesis failed, sending text-only (playback_id=%s)",
                request.playback_id,
            )

        # 새 WSMessage로 재포장 (audio_url 채움)
        out = WSMessage.make_tts_play(request, state_version=msg.state_version)
        await self._send(out)

    # ── inbound: frontend → AudioManager ──────────────────────────────────────

    def handle_ack(self, playback_id: str, status: str) -> None:
        """frontend가 재생 완료/중단 통보. 현재는 로깅만, M2에서 큐 진행 트리거."""
        logger.debug("audio_ack: playback_id=%s status=%s", playback_id, status)

    # ── 외부 호출용 enqueue API ───────────────────────────────────────────────

    async def enqueue_tts(
        self,
        text: str,
        agent: str = "narrator",
        priority: AudioPriority = AudioPriority.NORMAL,
        sequence_id: str | None = None,
        seq_index: int = 0,
        state_version: int = 0,
    ) -> str:
        """FSM 외부에서 직접 TTS를 큐에 넣을 때 (테스트/디버깅용).

        Returns: playback_id
        """
        req = TTSRequest(
            text=text,
            priority=priority,
            agent=agent,
            playback_id=_new_playback_id(),
            sequence_id=sequence_id,
            seq_index=seq_index,
            state_version=state_version,
        )
        msg = WSMessage.make_tts_play(req, state_version=state_version)
        await self._handle_tts_play(msg)
        assert req.playback_id is not None
        return req.playback_id

    async def enqueue_sfx(
        self,
        name: str,
        priority: AudioPriority = AudioPriority.NORMAL,
        sequence_id: str | None = None,
        seq_index: int = 0,
    ) -> str:
        """효과음 재생. catalog.SFX_REGISTRY에서 audio_url 조회."""
        from audio.catalog import SFX_REGISTRY

        audio_url = SFX_REGISTRY.get(name)
        if audio_url is None:
            logger.warning("enqueue_sfx: unknown SFX name=%r", name)
            return ""
        req = SFXRequest(
            name=name,
            audio_url=audio_url,
            priority=priority,
            playback_id=_new_playback_id(),
            sequence_id=sequence_id,
            seq_index=seq_index,
        )
        msg = WSMessage.make_sfx_play(req)
        await self._send(msg)
        assert req.playback_id is not None
        return req.playback_id

    async def enqueue_llm_line(
        self,
        agent: str,
        text: str,
        priority: AudioPriority = AudioPriority.NORMAL,
        sequence_id: str | None = None,
        seq_index: int = 0,
    ) -> str:
        """LLM 멀티에이전트 멘트 진입점 (승경팀용).

        승경팀 사용 예:
            await mgr.enqueue_llm_line(
                agent="referee", text="규칙 위반!", priority=AudioPriority.CRITICAL,
            )
        """
        return await self.enqueue_tts(
            text=text,
            agent=agent,
            priority=priority,
            sequence_id=sequence_id,
            seq_index=seq_index,
        )

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _voice_for(self, request: TTSRequest) -> VoiceConfig:
        """request.text가 EXCITED_LINES이면 EXCITED_VOICE, 그 외엔 agent별."""
        if request.text in EXCITED_LINES:
            return EXCITED_VOICE
        return VOICE_BY_AGENT.get(request.agent, DEFAULT_VOICE)

    def _layer_for(self, text: str) -> tuple[CacheLayer, str | None]:
        """text의 캐시 계층과 session_id 반환.

        - STATIC/EXCITED → ("static", None)
        - SESSION 템플릿 매칭 → ("session", active_session_id)
        - 그 외 → ("dynamic", None)
        """
        if text in EXCITED_LINES:
            return "static", None
        category = classify_text(text)
        if category == "static":
            return "static", None
        if category == "session" and self._active_session_id is not None:
            return "session", self._active_session_id
        return "dynamic", None

    @staticmethod
    def _audio_url_for(
        path: Any, layer: CacheLayer, session_id: str | None
    ) -> str:
        """디스크 경로 → frontend가 접근할 URL.

        server.py가 StaticFiles로 다음을 마운트한 가정:
            /cache/tts/static/  → audio/assets/tts_cache/static/
            /cache/tts/session/ → audio/assets/tts_cache/session/
            /cache/tts/dynamic/ → audio/assets/tts_cache/dynamic/
        """
        filename = path.name if hasattr(path, "name") else str(path).rsplit("/", 1)[-1]
        if layer == "session" and session_id:
            return f"/cache/tts/session/{session_id}/{filename}"
        return f"/cache/tts/{layer}/{filename}"

    async def _send(self, msg: WSMessage) -> None:
        if self._broadcast is None:
            logger.debug(
                "AudioManager._send: no broadcast attached, dropping msg_type=%s",
                msg.msg_type,
            )
            return
        try:
            await self._broadcast(msg)
        except Exception:
            logger.exception("AudioManager broadcast failed (msg_type=%s)", msg.msg_type)
