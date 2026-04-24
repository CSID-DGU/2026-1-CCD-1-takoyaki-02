"""TTS/오디오 메시지 타입. Phase 1부터 FSM이 TTS 재생 요청에 사용."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any


class AudioType(StrEnum):
    TTS = "tts"
    SFX = "sfx"
    BGM = "bgm"


class AudioPriority(IntEnum):
    CRITICAL = 1  # 규칙 위반
    HIGH = 2  # 템포
    NORMAL = 3  # 일반 멘트
    LOW = 4  # BGM


@dataclass
class TTSRequest:
    text: str
    audio_url: str | None = None  # 미리 캐시된 wav 경로
    audio_type: AudioType = AudioType.TTS
    priority: AudioPriority = AudioPriority.NORMAL
    agent: str = "narrator"  # AgentRole.value
    interruptible: bool = True
    playback_id: str | None = None
    state_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "audio_url": self.audio_url,
            "audio_type": self.audio_type.value,
            "priority": self.priority.value,
            "agent": self.agent,
            "interruptible": self.interruptible,
            "playback_id": self.playback_id,
            "state_version": self.state_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TTSRequest:
        return cls(
            text=d["text"],
            audio_url=d.get("audio_url"),
            audio_type=AudioType(d.get("audio_type", AudioType.TTS.value)),
            priority=AudioPriority(d.get("priority", AudioPriority.NORMAL.value)),
            agent=d.get("agent", "narrator"),
            interruptible=bool(d.get("interruptible", True)),
            playback_id=d.get("playback_id"),
            state_version=int(d.get("state_version", 0)),
        )
