"""WebSocket endpoint feeding the live dashboard.

Frame contract (server -> client), all JSON:

  {"type": "snapshot",  "server_time": str, "backend": {...}, "devices": [...], "events": [...]}
  {"type": "telemetry", "server_time": str, "device": {...}}
  {"type": "events",    "server_time": str, "device_id": str, "events": [...]}
  {"type": "device",    "server_time": str, "device": {...}}
  {"type": "pong",      "server_time": str}

Client -> server frames are ignored except for keepalive payloads, which exist so
proxies do not idle out the socket.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.services import realtime
from app.websocket import Client, manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])

KEEPALIVE_INTERVAL_S = 20.0
CLIENT_SEND_TIMEOUT_S = 5.0


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: str | None = Query(default=None, max_length=64),
) -> None:
    client = Client(client_id=uuid4().hex, websocket=websocket)
    session: Session = get_session_factory()()
    try:
        await manager.connect(client)
        logger.info("websocket client connected id=%s clients=%d", client.client_id, manager.client_count)

        snapshot = realtime.build_snapshot(session)
        snapshot["device_filter"] = device_id
        client.offer(snapshot)

        sender = asyncio.create_task(_pump(client))
        try:
            while True:
                _handle_client_message(client, await websocket.receive_text())
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
    except Exception:  # pragma: no cover - transport level failure
        logger.exception("websocket session failed id=%s", client.client_id)
    finally:
        await manager.disconnect(client.client_id)
        session.close()
        logger.info("websocket client disconnected id=%s", client.client_id)


@router.websocket("/ws/{device_id}")
async def websocket_endpoint_for_device(websocket: WebSocket, device_id: str) -> None:
    await websocket_endpoint(websocket, device_id=device_id)


def _handle_client_message(client: Client, message: str) -> None:
    """Answer a client keepalive immediately and ignore anything else.

    Replying without waiting for the idle timer lets the console confirm liveness
    on demand instead of inferring it, and stops proxies from idling the socket
    out. Unknown or malformed frames are dropped silently: the dashboard is a
    read-only observer, so there is nothing else it may ask for.
    """
    try:
        payload = json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return
    if isinstance(payload, dict) and payload.get("type") == "ping":
        client.offer({"type": realtime.FRAME_PONG, "server_time": realtime.server_time_iso()})


async def _pump(client: Client) -> None:
    """Forward queued frames, emitting a keepalive only when the queue stays idle.

    The idle wait is what makes the keepalive safe: a sleep between frames would
    add that delay to every live update.
    """
    while True:
        try:
            frame = await asyncio.wait_for(
                client.queue.get(), timeout=KEEPALIVE_INTERVAL_S
            )
        except asyncio.TimeoutError:
            frame = {"type": realtime.FRAME_PONG, "server_time": realtime.server_time_iso()}

        try:
            await asyncio.wait_for(client.websocket.send_json(frame), timeout=CLIENT_SEND_TIMEOUT_S)
        except (asyncio.TimeoutError, WebSocketDisconnect, RuntimeError):
            logger.info("websocket send failed id=%s dropped_frames=%s", client.client_id, client.dropped_frames)
            return
