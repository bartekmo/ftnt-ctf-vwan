"""
WebSocket connection manager.
Broadcasts score updates to all connected clients.
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps channel name -> set of websockets
        self._channels: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "scoreboard"):
        await websocket.accept()
        async with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(websocket)
        logger.info(f"WS connected to channel '{channel}', total: {len(self._channels[channel])}")

    async def disconnect(self, websocket: WebSocket, channel: str = "scoreboard"):
        async with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(websocket)
        logger.info(f"WS disconnected from channel '{channel}'")

    async def broadcast(self, data: dict, channel: str = "scoreboard"):
        if channel not in self._channels:
            return
        dead = set()
        payload = json.dumps(data)
        for ws in list(self._channels[channel]):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._channels[channel] -= dead

    async def broadcast_scoreboard_update(self, scoreboard_data: dict):
        await self.broadcast({"type": "scoreboard_update", "data": scoreboard_data})

    async def broadcast_solve(self, solve_data: dict):
        await self.broadcast({"type": "new_solve", "data": solve_data})

    async def broadcast_event_status(self, status: str):
        await self.broadcast({"type": "event_status", "data": {"status": status}})


manager = ConnectionManager()
