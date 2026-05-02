"""WebSocket /ws/tablet 핸들러.

연결 시 현재 state 즉시 push, 이후 orchestrator가 broadcast할 때마다 state_update 전송.
클라이언트 input 수신 → orchestrator.handle_input으로 위임.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


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
        await websocket.send_text(
            json.dumps({"msg_type": "state_update", "state": snapshot})
        )

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("msg_type") == "input":
                    orchestrator.handle_input(
                        msg.get("input_type", ""),
                        msg.get("data", {}),
                    )
            except (json.JSONDecodeError, Exception):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
