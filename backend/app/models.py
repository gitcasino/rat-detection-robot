"""Relational model: devices, immutable events, telemetry samples, emitter sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain import DeviceState, EventType, RobotState, TelemetrySource
from app.timeutils import utcnow


class Device(Base):
    """Latest known state of one robot. Rows are created on first telemetry."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(
        String(16), default=DeviceState.ONLINE.value, nullable=False, index=True
    )
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    emitter_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emitter_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    emitter_active_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    emitter_activations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    robot_state: Mapped[str] = mapped_column(
        String(32), default=RobotState.IDLE.value, nullable=False
    )

    distance_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vibration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ir_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wifi_ssid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wifi_rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    uptime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    events: Mapped[list[Event]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Event(Base):
    """Immutable history record. Append-only by design; no update path exists."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str] = mapped_column(
        String(24), default=TelemetrySource.DEVICE.value, nullable=False
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    device_timestamp_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    distance_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ir_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    emitter_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    robot_state: Mapped[str | None] = mapped_column(String(32), nullable=True)

    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    device: Mapped[Device] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_events_device_received", "device_id", "received_at"),
        Index("ix_events_type_received", "event_type", "received_at"),
    )


class TelemetrySample(Base):
    """Rate-limited state snapshot. High-frequency readings are aggregated away."""

    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    uptime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ir_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emitter_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    robot_state: Mapped[str] = mapped_column(String(32), nullable=False)
    wifi_rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (Index("ix_telemetry_device_received", "device_id", "received_at"),)


class EmitterSession(Base):
    """One activation window. `duration_seconds` is null while the emitter is still active."""

    __tablename__ = "emitter_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False
    )
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    activation_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deactivation_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_emitter_sessions_device_activated", "device_id", "activated_at"),)


def event_type_values() -> list[str]:
    return [member.value for member in EventType]
