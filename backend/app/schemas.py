"""Request and response contracts.

Ingestion models intentionally allow unknown fields so that a newer firmware can
add payload sections without breaking the server. Validation of the fields the
server actually relies on stays strict.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import (
    DeviceState,
    EventCategory,
    EventType,
    RobotState,
    TelemetrySource,
    category_for,
)
from app.timeutils import as_utc, parse_device_timestamp

TELEMETRY_SCHEMA_VERSION = 1
MAX_EVENTS_PER_REQUEST = 64
MAX_DISTANCE_CM = 1000.0
MAX_METADATA_BYTES = 4096


class TelemetryBase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class EmitterStateIn(TelemetryBase):
    active: bool = False
    mode: str | None = Field(default=None, max_length=48)
    commanded_by: str | None = Field(default=None, max_length=48)


class SensorStateIn(TelemetryBase):
    vibration: bool = False
    ir: bool = Field(default=False, alias="ir_detected")
    distance_cm: float | None = Field(default=None, ge=0, le=MAX_DISTANCE_CM)
    distance_valid: bool = True

    @field_validator("distance_cm")
    @classmethod
    def _reject_nan(cls, value: float | None) -> float | None:
        if value is not None and value != value:  # NaN
            raise ValueError("distance_cm must be a real number")
        return value


class RobotStateIn(TelemetryBase):
    state: RobotState = RobotState.IDLE
    left_motor: int | None = Field(default=None, ge=-100, le=100)
    right_motor: int | None = Field(default=None, ge=-100, le=100)
    obstacle_distance_cm: float | None = Field(default=None, ge=0, le=MAX_DISTANCE_CM)


class NetworkStateIn(TelemetryBase):
    rssi: int | None = Field(default=None, ge=-127, le=0)
    ip: str | None = Field(default=None, max_length=45)
    ssid: str | None = Field(default=None, max_length=64)
    channel: int | None = Field(default=None, ge=1, le=14)


class TelemetryIn(TelemetryBase):
    schema_version: int = Field(default=TELEMETRY_SCHEMA_VERSION, ge=1, le=1000)
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    timestamp: datetime | None = None
    uptime_ms: int | None = Field(default=None, ge=0)
    emitter: EmitterStateIn = Field(default_factory=EmitterStateIn)
    sensors: SensorStateIn = Field(default_factory=SensorStateIn)
    robot: RobotStateIn = Field(default_factory=RobotStateIn)
    network: NetworkStateIn = Field(default_factory=NetworkStateIn)
    firmware_version: str | None = Field(default=None, max_length=32)

    @field_validator("device_id")
    @classmethod
    def _normalise_device_id(cls, value: str) -> str:
        return value.strip()

    def device_timestamp(self) -> datetime | None:
        return parse_device_timestamp(self.timestamp)


class TelemetryAck(BaseModel):
    accepted: bool = True
    device_id: str
    received_at: datetime
    server_time_ms: int
    events: list["EventOut"] = Field(default_factory=list)
    device_state: DeviceState


class EventIn(TelemetryBase):
    type: EventType
    timestamp: datetime | int | float | str | None = None
    uptime_ms: int | None = Field(default=None, ge=0)
    distance_cm: float | None = Field(default=None, ge=0, le=MAX_DISTANCE_CM)
    vibration: bool | None = None
    ir_detected: bool | None = None
    emitter_active: bool | None = None
    robot_state: RobotState | None = None
    message: str | None = Field(default=None, max_length=255)
    detail: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None

    def parsed_timestamp(self) -> datetime | None:
        return parse_device_timestamp(self.timestamp)


class EventBatchIn(TelemetryBase):
    schema_version: int = Field(default=TELEMETRY_SCHEMA_VERSION, ge=1, le=1000)
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    events: list[EventIn] = Field(min_length=1, max_length=MAX_EVENTS_PER_REQUEST)
    uptime_ms: int | None = Field(default=None, ge=0)

    @field_validator("device_id")
    @classmethod
    def _normalise_device_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("events")
    @classmethod
    def _bound_metadata(cls, value: list[EventIn]) -> list[EventIn]:
        for item in value:
            if item.metadata is not None:
                size = len(str(item.metadata).encode("utf-8"))
                if size > MAX_METADATA_BYTES:
                    raise ValueError(f"metadata exceeds {MAX_METADATA_BYTES} bytes")
        return value


class EventBatchAck(BaseModel):
    accepted: bool = True
    device_id: str
    received_at: datetime
    accepted_count: int
    duplicates: list[str] = Field(default_factory=list)
    events: list["EventOut"] = Field(default_factory=list)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    device_id: str
    event_type: EventType
    category: EventCategory
    source: TelemetrySource
    occurred_at: datetime
    received_at: datetime
    device_timestamp_rejected: bool = False
    distance_cm: float | None = None
    vibration: bool | None = None
    ir_detected: bool | None = None
    emitter_active: bool | None = None
    robot_state: RobotState | None = None
    message: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    emitter_duration_seconds: float | None = None

    @classmethod
    def from_model(cls, row: Any) -> "EventOut":
        meta = dict(row.metadata_ or {})
        duration = meta.get("emitter_duration_seconds")
        return cls(
            id=row.id,
            device_id=row.device_id,
            event_type=EventType(row.event_type),
            category=category_for(EventType(row.event_type)),
            source=TelemetrySource(row.source),
            occurred_at=as_utc(row.occurred_at),
            received_at=as_utc(row.received_at),
            device_timestamp_rejected=row.device_timestamp_rejected,
            distance_cm=row.distance_cm,
            vibration=row.vibration,
            ir_detected=row.ir_detected,
            emitter_active=row.emitter_active,
            robot_state=RobotState(row.robot_state) if row.robot_state else None,
            message=row.message,
            detail=row.detail,
            metadata_=meta or None,
            emitter_duration_seconds=duration if isinstance(duration, (int, float)) else None,
        )


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    offset: int


class EmitterSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    activated_at: datetime
    deactivated_at: datetime | None = None
    duration_seconds: float | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    label: str | None = None
    state: DeviceState
    emitter_active: bool
    emitter_activated_at: datetime | None = None
    emitter_active_seconds: float = 0.0
    emitter_activations: int = 0
    robot_state: RobotState
    distance_cm: float | None = None
    distance_updated_at: datetime | None = None
    vibration: bool = False
    ir_detected: bool = False
    wifi_ssid: str | None = None
    wifi_rssi: int | None = None
    ip_address: str | None = None
    uptime_ms: int | None = None
    firmware_version: str | None = None
    schema_version: int = 1
    first_seen_at: datetime
    last_seen_at: datetime
    last_telemetry_at: datetime | None = None
    last_event_at: datetime | None = None
    offline_since: datetime | None = None
    offline_count: int = 0
    open_session: EmitterSessionOut | None = None

    @classmethod
    def from_model(cls, row: Any, open_session: EmitterSessionOut | None = None) -> "DeviceOut":
        return cls(
            device_id=row.device_id,
            label=row.label,
            state=DeviceState(row.state),
            emitter_active=row.emitter_active,
            emitter_activated_at=as_utc(row.emitter_activated_at),
            emitter_active_seconds=row.emitter_active_seconds or 0.0,
            emitter_activations=row.emitter_activations or 0,
            robot_state=RobotState(row.robot_state),
            distance_cm=row.distance_cm,
            distance_updated_at=as_utc(row.distance_updated_at),
            vibration=bool(row.vibration),
            ir_detected=bool(row.ir_detected),
            wifi_ssid=row.wifi_ssid,
            wifi_rssi=row.wifi_rssi,
            ip_address=row.ip_address,
            uptime_ms=row.uptime_ms,
            firmware_version=row.firmware_version,
            schema_version=row.schema_version,
            first_seen_at=as_utc(row.first_seen_at),
            last_seen_at=as_utc(row.last_seen_at),
            last_telemetry_at=as_utc(row.last_telemetry_at),
            last_event_at=as_utc(row.last_event_at),
            offline_since=as_utc(row.offline_since),
            offline_count=row.offline_count or 0,
            open_session=open_session,
        )


class LinkStatus(BaseModel):
    """Transport health, independent of the robot itself."""

    websocket: Literal["connected", "disconnected"] = "disconnected"
    websocket_clients: int = 0
    backend: Literal["online", "offline"] = "online"


class StatusOut(BaseModel):
    server_time: datetime
    backend: LinkStatus
    device_count: int
    devices_online: int
    devices_offline: int
    primary_device_id: str | None = None
    devices: list[DeviceOut] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    uptime_seconds: float
    database: Literal["ok", "error"]
    server_time: datetime
    devices: int
    devices_online: int
    websocket_clients: int
    telemetry_schema_version: int = TELEMETRY_SCHEMA_VERSION


class StatBucket(BaseModel):
    bucket: datetime
    count: int


class StatsOut(BaseModel):
    generated_at: datetime
    window_hours: int
    total_events: int
    events_in_window: int
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_category: dict[str, int] = Field(default_factory=dict)
    emitter_activations: int
    emitter_active_seconds: float
    emitter_average_seconds: float | None = None
    emitter_longest_seconds: float | None = None
    emitter_open_session: EmitterSessionOut | None = None
    events_per_bucket: list[StatBucket] = Field(default_factory=list)
    devices_by_state: dict[str, int] = Field(default_factory=dict)
    last_event_at: datetime | None = None
    events_per_hour: dict[str, int] = Field(default_factory=dict)


class ErrorOut(BaseModel):
    detail: str
    error: str | None = None


TelemetryAck.model_rebuild()
