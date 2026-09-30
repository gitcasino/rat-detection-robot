"""Device registry: presence, state projection and heartbeat expiry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import DeviceState, RobotState
from app.models import Device, EmitterSession, Event
from app.schemas import TelemetryIn
from app.timeutils import utcnow


@dataclass(frozen=True)
class DevicePresence:
    device: Device
    is_new: bool
    was_offline: bool
    became_online: bool


def get_device(session: Session, device_id: str) -> Device | None:
    return session.get(Device, device_id)


def list_devices(session: Session) -> list[Device]:
    return list(session.scalars(select(Device).order_by(Device.device_id)))


def get_or_create_device(session: Session, device_id: str, now: datetime | None = None) -> Device:
    now = now or utcnow()
    device = session.get(Device, device_id)
    if device is not None:
        return device
    device = Device(
        device_id=device_id,
        state=DeviceState.ONLINE.value,
        first_seen_at=now,
        last_seen_at=now,
        robot_state=RobotState.IDLE.value,
    )
    session.add(device)
    session.flush()
    return device


def register_presence(
    session: Session,
    device_id: str,
    now: datetime | None = None,
    label: str | None = None,
) -> DevicePresence:
    """Create the device if unknown and refresh its connectivity state."""
    now = now or utcnow()
    existing = session.get(Device, device_id)
    is_new = existing is None
    device = existing or get_or_create_device(session, device_id, now=now)

    was_offline = device.state == DeviceState.OFFLINE.value
    device.state = DeviceState.ONLINE.value
    device.offline_since = None
    device.last_seen_at = now
    if label:
        device.label = label

    return DevicePresence(
        device=device,
        is_new=is_new,
        was_offline=was_offline,
        became_online=is_new or was_offline,
    )


def apply_telemetry_to_device(device: Device, payload: TelemetryIn, now: datetime) -> None:
    """Project a telemetry frame onto the device row (no side effects beyond state)."""
    device.last_seen_at = now
    device.last_telemetry_at = now
    device.uptime_ms = payload.uptime_ms
    device.emitter_active = payload.emitter.active
    device.robot_state = payload.robot.state.value
    device.vibration = payload.sensors.vibration
    device.ir_detected = payload.sensors.ir
    device.schema_version = payload.schema_version

    if payload.sensors.distance_cm is not None:
        device.distance_cm = payload.sensors.distance_cm
        device.distance_updated_at = now

    if payload.network.rssi is not None:
        device.wifi_rssi = payload.network.rssi
    if payload.network.ip:
        device.ip_address = payload.network.ip
    if payload.network.ssid:
        device.wifi_ssid = payload.network.ssid
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version


def expired_device_ids(session: Session, now: datetime, timeout_s: float) -> list[str]:
    cutoff = now - timedelta(seconds=timeout_s)
    rows = session.scalars(
        select(Device.device_id).where(
            Device.state != DeviceState.OFFLINE.value,
            Device.last_seen_at < cutoff,
        )
    )
    return list(rows)


def mark_offline(session: Session, device_id: str, now: datetime | None = None) -> Device | None:
    now = now or utcnow()
    device = session.get(Device, device_id)
    if device is None or device.state == DeviceState.OFFLINE.value:
        return None
    device.state = DeviceState.OFFLINE.value
    device.offline_since = now
    device.offline_count = (device.offline_count or 0) + 1
    return device


def mark_online(session: Session, device_id: str, now: datetime | None = None) -> Device | None:
    now = now or utcnow()
    device = session.get(Device, device_id)
    if device is None:
        return None
    changed = device.state == DeviceState.OFFLINE.value
    device.state = DeviceState.ONLINE.value
    device.offline_since = None
    device.last_seen_at = now
    return device if changed else None


def count_online(session: Session) -> int:
    return len(
        list(
            session.scalars(
                select(Device.device_id).where(Device.state == DeviceState.ONLINE.value)
            )
        )
    )


def open_emitter_session(session: Session, device_id: str) -> EmitterSession | None:
    return session.scalars(
        select(EmitterSession)
        .where(EmitterSession.device_id == device_id, EmitterSession.deactivated_at.is_(None))
        .order_by(EmitterSession.activated_at.desc())
    ).first()


def last_event(session: Session, device_id: str) -> Event | None:
    return session.scalars(
        select(Event).where(Event.device_id == device_id).order_by(Event.id.desc())
    ).first()
