"""WebSocket /ws/tablet 핸들러.

연결 시 현재 state 즉시 push, 이후 orchestrator가 broadcast할 때마다 state_update 전송.
클라이언트 input 수신 → orchestrator.handle_input으로 위임.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# 처리 오류가 이 횟수만큼 연속 발생하면 연결을 종료해 폭주 방지.
_MAX_CONSECUTIVE_ERRORS = 5


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections = [c for c in self._connections if c is not ws]

    async def broadcast(self, snapshot: dict) -> None:
        msg = json.dumps({"msg_type": "state_update", "state": snapshot})
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def tablet_ws_handler(websocket: WebSocket, orchestrator: Any) -> None:
    await manager.connect(websocket)
    try:
        # 연결 즉시 현재 state push
        snapshot = orchestrator.current_snapshot()
        await websocket.send_text(json.dumps({"msg_type": "state_update", "state": snapshot}))

        consecutive_errors = 0
        while True:
            raw = await websocket.receive_text()

            # 1) JSON 파싱 — 실패 시 클라이언트에 에러 응답
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning("ws/tablet: invalid JSON from client: %s", e)
                with contextlib.suppress(Exception):
                    await websocket.send_text(
                        json.dumps({"msg_type": "error", "error": "invalid_json"})
                    )
                continue

            if msg.get("msg_type") != "input":
                # 미지원 msg_type은 무시 (확장 여지)
                continue

            # 2) 처리 — 연속 실패 카운트, 임계 초과 시 연결 종료
            try:
                orchestrator.handle_input(
                    msg.get("input_type", ""),
                    msg.get("data", {}),
                )
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                logger.exception(
                    "ws/tablet: handle_input failed (input_type=%s, count=%d)",
                    msg.get("input_type"),
                    consecutive_errors,
                )
                with contextlib.suppress(Exception):
                    await websocket.send_text(
                        json.dumps({"msg_type": "error", "error": "handler_failed"})
                    )
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        "ws/tablet: closing connection after %d consecutive errors",
                        consecutive_errors,
                    )
                    break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
