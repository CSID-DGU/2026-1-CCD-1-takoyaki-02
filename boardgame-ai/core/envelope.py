"""WebSocket 메시지 공통 봉투."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.audio import TTSRequest
from core.constants import MsgType
from core.events import FusionContext, GameEvent


@dataclass
class WSMessage:
    msg_type: str
    payload: dict[str, Any]
    state_version: int = 0
    msg_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_type": self.msg_type,
            "payload": self.payload,
            "state_version": self.state_version,
            "msg_id": self.msg_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WSMessage:
        return cls(
            msg_type=d["msg_type"],
            payload=dict(d["payload"]),
            state_version=int(d.get("state_version", 0)),
            msg_id=d["msg_id"],
            timestamp=float(d["timestamp"]),
        )

    @classmethod
    def make_game_event(cls, event: GameEvent, state_version: int = 0) -> WSMessage:
        return cls(
            msg_type=MsgType.GAME_EVENT.value,
            payload=event.to_dict(),
            state_version=state_version,
            msg_id=f"evt_{uuid.uuid4().hex[:12]}",
        )

    @classmethod
    def make_fusion_context(cls, context: FusionContext, state_version: int = 0) -> WSMessage:
        return cls(
            msg_type=MsgType.FUSION_CONTEXT.value,
            payload=context.to_dict(),
            state_version=state_version,
            msg_id=f"ctx_{uuid.uuid4().hex[:12]}",
        )

    @classmethod
    def make_tts_play(cls, request: TTSRequest, state_version: int = 0) -> WSMessage:
        return cls(
            msg_type=MsgType.TTS_PLAY.value,
            payload=request.to_dict(),
            state_version=state_version,
            msg_id=f"tts_{uuid.uuid4().hex[:12]}",
        )

    @classmethod
    def make_tts_interrupt(
        cls, playback_id: str | None = None, state_version: int = 0
    ) -> WSMessage:
        return cls(
            msg_type=MsgType.TTS_INTERRUPT.value,
            payload={"playback_id": playback_id},
            state_version=state_version,
            msg_id=f"int_{uuid.uuid4().hex[:12]}",
        )

    @classmethod
    def make_hello(cls, info: dict[str, Any] | None = None) -> WSMessage:
        return cls(
            msg_type=MsgType.HELLO.value,
            payload=info or {},
            msg_id=f"hello_{uuid.uuid4().hex[:12]}",
        )

    @classmethod
    def make_error(cls, code: str, message: str, state_version: int = 0) -> WSMessage:
        return cls(
            msg_type=MsgType.ERROR.value,
            payload={"code": code, "message": message},
            state_version=state_version,
            msg_id=f"err_{uuid.uuid4().hex[:12]}",
        )
