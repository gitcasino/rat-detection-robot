"""Frame construction and fan-out for the live dashboard stream."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models import Device, Event
from app.schemas import DeviceOut, EmitterSessionOut, EventOut
from app.services import devices as device_service
from app.services import events as event_service
from app.timeutils import as_utc, utcnow
from app.websocket import manager

logger = logging.getLogger(__name__)

FRAME_SNAPSHOT = "snapshot"
FRAME_TELEMETRY = "telemetry"
FRAME_EVENTS = "events"
FRAME_DEVICE = "device"
FRAME_PONG = "pong"
FRAME_ERROR = "error"


def server_time_iso() -> str:
    """UTC timestamp in the same shape REST responses use (trailing ``Z``)."""
    return as_utc(utcnow()).isoformat().replace("+00:00", "Z")


def serialise_device(session: Session, device: Device) -> dict[str, Any]:
    open_session = device_service.open_emitter_session(session, device.device_id)
    payload = DeviceOut.from_model(
        device,
        open_session=EmitterSessionOut.model_validate(open_session, from_attributes=True)
        if open_session
        else None,
    )
    return payload.model_dump(mode="json")


def serialise_events(rows: Iterable[Event]) -> list[dict[str, Any]]:
    return [EventOut.from_model(row).model_dump(mode="json") for row in rows]


def build_snapshot(session: Session, recent_limit: int = 50) -> dict[str, Any]:
    devices = device_service.list_devices(session)
    recent = event_service.recent_events(session, None, limit=recent_limit)
    return {
        "type": FRAME_SNAPSHOT,
        "server_time": server_time_iso(),
        "backend": {
            "websocket": "connected",
            "websocket_clients": manager.client_count,
            "backend": "online",
        },
        "devices": [serialise_device(session, device) for device in devices],
        "events": serialise_events(reversed(recent)),
    }


async def broadcast_device_state(session: Session, device: Device) -> None:
    await manager.broadcast(
        {
            "type": FRAME_TELEMETRY,
            "server_time": server_time_iso(),
            "device": serialise_device(session, device),
        }
    )


async def broadcast_events(device_id: str, rows: Iterable[Event]) -> None:
    rows = list(rows)
    if not rows:
        return
    await manager.broadcast(
        {
            "type": FRAME_EVENTS,
            "server_time": server_time_iso(),
            "device_id": device_id,
            "events": serialise_events(rows),
        }
    )


async def publish_telemetry(session: Session, device: Device, rows: Iterable[Event]) -> None:
    """One telemetry frame produces one state frame plus one event frame.

    The state frame carries the full authoritative device state, so a dashboard
    that missed an earlier frame resynchronises on the next one.
    """
    rows = list(rows)
    await broadcast_device_state(session, device)
    await broadcast_events(device.device_id, rows)


async def publish_device(device: Device) -> None:
    await manager.broadcast(
        {
            "type": FRAME_DEVICE,
            "server_time": server_time_iso(),
            "device": DeviceOut.from_model(device).model_dump(mode="json"),
        }
    )
