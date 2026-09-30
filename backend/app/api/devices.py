"""Device registry, consolidated status and aggregate statistics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import session_dep
from app.domain import DeviceState
from app.schemas import DeviceOut, EmitterSessionOut, StatsOut, StatusOut
from app.services import devices as device_service
from app.services import stats as stats_service
from app.timeutils import as_utc, utcnow
from app.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=list[DeviceOut], summary="List known devices")
def list_devices(session: Session = Depends(session_dep)) -> list[DeviceOut]:
    return [_device_out(session, device) for device in device_service.list_devices(session)]


@router.get("/devices/{device_id}", response_model=DeviceOut, summary="Fetch one device state")
def get_device(device_id: str, session: Session = Depends(session_dep)) -> DeviceOut:
    device = device_service.get_device(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _device_out(session, device)


@router.get("/status", response_model=StatusOut, summary="Consolidated dashboard status")
def get_status(session: Session = Depends(session_dep)) -> StatusOut:
    devices = device_service.list_devices(session)
    online = [device for device in devices if device.state == DeviceState.ONLINE.value]
    offline = [device for device in devices if device.state == DeviceState.OFFLINE.value]
    primary = online[0] if online else (devices[0] if devices else None)

    return StatusOut(
        server_time=as_utc(utcnow()),
        backend={
            "websocket": "connected" if manager.client_count else "disconnected",
            "websocket_clients": manager.client_count,
            "backend": "online",
        },
        device_count=len(devices),
        devices_online=len(online),
        devices_offline=len(offline),
        primary_device_id=primary.device_id if primary else None,
        devices=[_device_out(session, device) for device in devices],
    )


@router.get("/stats", response_model=StatsOut, summary="Event and emitter statistics")
def get_stats(
    window_hours: int = Query(default=24, ge=1, le=24 * 30),
    session: Session = Depends(session_dep),
) -> StatsOut:
    return stats_service.compute_stats(session, window_hours=window_hours)


def _device_out(session: Session, device) -> DeviceOut:
    open_session = device_service.open_emitter_session(session, device.device_id)
    return DeviceOut.from_model(
        device,
        open_session=EmitterSessionOut.model_validate(open_session, from_attributes=True)
        if open_session
        else None,
    )
