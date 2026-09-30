"""WebSocket fan-out.

Broadcast is non-blocking from the caller's point of view: each client owns a
bounded queue, and a client that cannot keep up loses the oldest frames instead
of stalling ingestion. Losing an intermediate frame is preferable to blocking the
ingest path, and every frame carries the authoritative device state so the UI can
recover from a dropped frame on the next message.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

QUEUE_MAXSIZE = 256


@dataclass
class Client:
    client_id: str
    websocket: WebSocket
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(QUEUE_MAXSIZE))
    dropped_frames: int = 0

    def offer(self, message: dict[str, Any]) -> None:
        if self.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
                self.dropped_frames += 1
        self.queue.put_nowait(message)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def total_dropped(self) -> int:
        return sum(client.dropped_frames for client in self._clients.values())

    async def connect(self, client: Client) -> None:
        await client.websocket.accept()
        async with self._lock:
            self._clients[client.client_id] = client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    def snapshot(self) -> list[Client]:
        return list(self._clients.values())

    async def broadcast(self, message: dict[str, Any]) -> None:
        for client in self.snapshot():
            client.offer(message)

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        client = self._clients.get(client_id)
        if client is None:
            return False
        client.offer(message)
        return True

    async def shutdown(self) -> None:
        for client in self.snapshot():
            with contextlib.suppress(Exception):
                await client.websocket.close(code=1001)
        self._clients.clear()


manager = ConnectionManager()
