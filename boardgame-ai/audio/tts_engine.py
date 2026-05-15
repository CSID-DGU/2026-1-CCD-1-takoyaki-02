"""Google Cloud TTS 비동기 래퍼.

캐시 정책:
- cache_key = sha1(text + voice.name + speaking_rate + pitch).
- 결과 wav는 cache_layer에 따라 static/session/<id>/dynamic/ 하위에 저장.
- synthesize() 호출 시 캐시 hit이면 API 호출 0회, 즉시 Path 반환.

동시성:
- asyncio.Semaphore(2)로 동시 API 호출 제한 → quota burst 방지.

장애 처리:
- Google API 실패/타임아웃 시 None 반환. 상위(AudioManager)가 text-only fallback 결정.

환경:
- GOOGLE_APPLICATION_CREDENTIALS 환경변수가 서비스 계정 JSON 키 경로를 가리켜야 함.
- 미설정 시 TTSEngine.is_available() == False, synthesize는 즉시 None.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path

from audio.catalog import (
    DEFAULT_VOICE,
    DYNAMIC_CACHE_DIR,
    SESSION_CACHE_DIR,
    STATIC_CACHE_DIR,
    VoiceConfig,
)

logger = logging.getLogger(__name__)

# Google SDK는 lazy import — credential 없이도 모듈 import는 통과해야 테스트가 쉬워짐.
_texttospeech = None
_AudioEncoding = None


def _lazy_import_google() -> bool:
    global _texttospeech, _AudioEncoding
    if _texttospeech is not None:
        return True
    try:
        from google.cloud import texttospeech as _tts  # type: ignore[import-not-found]

        _texttospeech = _tts
        _AudioEncoding = _tts.AudioEncoding
        return True
    except ImportError:
        logger.warning("google-cloud-texttospeech not installed; TTS disabled")
        return False


CacheLayer = str  # "static" | "session" | "dynamic"


def _cache_dir_for(layer: CacheLayer, session_id: str | None = None) -> Path:
    if layer == "static":
        return STATIC_CACHE_DIR
    if layer == "session":
        if not session_id:
            raise ValueError("session layer requires session_id")
        return SESSION_CACHE_DIR / session_id
    if layer == "dynamic":
        return DYNAMIC_CACHE_DIR
    raise ValueError(f"unknown cache layer: {layer}")


def _make_cache_key(text: str, voice: VoiceConfig) -> str:
    """텍스트 + 보이스 설정 → sha1 16자 hex."""
    raw = f"{text}|{voice.name}|{voice.language_code}|{voice.speaking_rate}|{voice.pitch}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class TTSEngine:
    """Google Cloud TTS 합성 + 디스크 캐시.

    Usage:
        engine = TTSEngine()
        path = await engine.synthesize("안녕하세요", voice, "static")
    """

    def __init__(self, max_concurrency: int = 4, timeout_sec: float = 4.0) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._timeout = timeout_sec
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        if not _lazy_import_google():
            return
        creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds or not Path(creds).exists():
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS not set or file missing; TTS disabled "
                "(set in .env to enable Google Cloud TTS)"
            )
            return
        try:
            self._client = _texttospeech.TextToSpeechClient()
            self._available = True
            logger.info("TTSEngine ready (credentials=%s)", creds)
        except Exception:
            logger.exception("Failed to init Google TTS client")

    def is_available(self) -> bool:
        return self._available

    def cache_path(
        self,
        text: str,
        voice: VoiceConfig | None = None,
        cache_layer: CacheLayer = "dynamic",
        session_id: str | None = None,
    ) -> Path:
        """text/voice/layer로 결정되는 캐시 파일 경로(존재 여부 무관)."""
        v = voice or DEFAULT_VOICE
        key = _make_cache_key(text, v)
        return _cache_dir_for(cache_layer, session_id) / f"{key}.wav"

    def cache_hit(
        self,
        text: str,
        voice: VoiceConfig | None = None,
        cache_layer: CacheLayer = "dynamic",
        session_id: str | None = None,
    ) -> Path | None:
        path = self.cache_path(text, voice, cache_layer, session_id)
        return path if path.exists() else None

    async def synthesize(
        self,
        text: str,
        voice: VoiceConfig | None = None,
        cache_layer: CacheLayer = "dynamic",
        session_id: str | None = None,
    ) -> Path | None:
        """텍스트 → wav 파일. 캐시 hit이면 즉시 반환, miss면 Google API 호출.

        반환: 캐시 파일 경로. 합성 실패 또는 SDK 미설치 시 None.
        """
        v = voice or DEFAULT_VOICE
        path = self.cache_path(text, v, cache_layer, session_id)

        if path.exists():
            return path

        if not self._available:
            logger.debug("synthesize: TTS unavailable, returning None for %r", text[:30])
            return None

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with self._semaphore:
                wav_bytes = await asyncio.wait_for(
                    asyncio.to_thread(self._synthesize_sync, text, v),
                    timeout=self._timeout,
                )
        except TimeoutError:
            logger.warning("synthesize: timeout after %.1fs for %r", self._timeout, text[:30])
            return None
        except Exception:
            logger.exception("synthesize: Google TTS API call failed for %r", text[:30])
            return None

        if not wav_bytes:
            return None

        # 원자성: 임시 파일에 쓰고 rename → 부분 쓰기로 인한 깨진 캐시 방지.
        tmp_path = path.with_suffix(".wav.tmp")
        tmp_path.write_bytes(wav_bytes)
        tmp_path.replace(path)
        logger.info("synthesized %d bytes → %s", len(wav_bytes), path.name)
        return path

    def _synthesize_sync(self, text: str, voice: VoiceConfig) -> bytes:
        """Google SDK 동기 호출. asyncio.to_thread로 감싸 비동기화."""
        assert self._client is not None
        assert _texttospeech is not None
        input_msg = _texttospeech.SynthesisInput(text=text)
        voice_params = _texttospeech.VoiceSelectionParams(
            language_code=voice.language_code,
            name=voice.name,
        )
        audio_config = _texttospeech.AudioConfig(
            audio_encoding=_AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            speaking_rate=voice.speaking_rate,
            pitch=voice.pitch,
        )
        response = self._client.synthesize_speech(
            input=input_msg,
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content  # bytes
