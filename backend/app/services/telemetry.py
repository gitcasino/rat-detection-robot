"""Telemetry ingestion: validate -> persist -> project state.

Two responsibilities live here.

1. Device events (vibration, IR, target activity, obstacles) are recorded as the
   device reports them, because the device owns the sensor-fusion decision.

2. Emitter command state and drive state are *also* reconciled server-side by
   comparing consecutive telemetry frames. That guarantees the event log can
   never silently miss an emitter transition, even if the device's own event
   packet is lost. The two paths are de-duplicated so a single transition
   produces exactly one row (see `services.events.DEDUPE_WINDOW_S`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import MOVING_STATES, EventType, RobotState, TelemetrySource
from app.models import Device, Event, TelemetrySample
from app.schemas import EventBatchIn, EventIn, TelemetryIn
from app.services import devices as device_service
from app.services import events as event_service
from app.services.events import EventDraft, RecordedEvent
from app.timeutils import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    device: Device
    created_events: list[Event]
    duplicates: list[Event]
    sample_written: bool


@dataclass(frozen=True)
class EventIngestResult:
    device: Device
    created_events: list[Event]
    duplicates: list[Event]

    @property
    def accepted_count(self) -> int:
        """Device-reported rows only; server lifecycle rows ride along in created_events."""
        return len([row for row in self.created_events if row.source == TelemetrySource.DEVICE.value])


@dataclass(frozen=True)
class _EventContext:
    received_at: datetime
    distance_cm: float | None
    vibration: bool | None
    ir_detected: bool | None
    emitter_active: bool | None
    robot_state: str


def resolve_event_time(
    device_timestamp: datetime | None, received_at: datetime, skew_tolerance_s: int
) -> tuple[datetime, bool]:
    """Prefer the device clock, but fall back to server time when it cannot be trusted.

    An ESP32 without NTP reports epoch 0 and a device with a wrong clock reports
    something arbitrary; neither may rewrite the authoritative history order.
    """
    if device_timestamp is None:
        return received_at, True
    if abs((device_timestamp - received_at).total_seconds()) > skew_tolerance_s:
        return received_at, True
    return device_timestamp, False


def should_persist_sample(session: Session, device_id: str, now: datetime, interval_s: float) -> bool:
    if interval_s <= 0:
        return False
    latest = session.scalar(
        select(func.max(TelemetrySample.received_at)).where(TelemetrySample.device_id == device_id)
    )
    if latest is None:
        return True
    return (now - latest).total_seconds() >= interval_s


def ingest_telemetry(
    session: Session,
    payload: TelemetryIn,
    *,
    sample_interval_s: float,
    clock_skew_tolerance_s: int,
) -> IngestResult:
    now = utcnow()
    presence = device_service.register_presence(session, payload.device_id, now=now)
    device = presence.device

    previous_emitter = bool(device.emitter_active)
    previous_robot_state = RobotState(device.robot_state)

    device_service.apply_telemetry_to_device(device, payload, now)

    created: list[Event] = []

    if presence.became_online:
        created.append(
            _record(
                session,
                device,
                EventDraft(
                    event_type=EventType.DEVICE_ONLINE,
                    occurred_at=now,
                    metadata={"reason": "first_contact" if presence.is_new else "reconnected"},
                    source=TelemetrySource.SERVER,
                ),
                received_at=now,
            ).row
        )

    context = _EventContext(
        received_at=now,
        distance_cm=payload.sensors.distance_cm if payload.sensors.distance_valid else None,
        vibration=payload.sensors.vibration,
        ir_detected=payload.sensors.ir,
        emitter_active=payload.emitter.active,
        robot_state=payload.robot.state.value,
    )

    created.extend(
        _record(session, device, draft, received_at=now).row
        for draft in _reconcile_drafts(
            previous_emitter=previous_emitter,
            previous_robot_state=previous_robot_state,
            emitter_active=payload.emitter.active,
            robot_state=payload.robot.state,
            context=context,
        )
    )

    sample_written = should_persist_sample(session, device.device_id, now, sample_interval_s)
    if sample_written:
        session.add(
            TelemetrySample(
                device_id=device.device_id,
                received_at=now,
                uptime_ms=payload.uptime_ms,
                distance_cm=payload.sensors.distance_cm,
                vibration=payload.sensors.vibration,
                ir_detected=payload.sensors.ir,
                emitter_active=payload.emitter.active,
                robot_state=payload.robot.state.value,
                wifi_rssi=payload.network.rssi,
                schema_version=payload.schema_version,
            )
        )

    session.commit()
    session.refresh(device)

    if created:
        logger.info(
            "device=%s telemetry uptime_ms=%s distance_cm=%s emitter=%s robot=%s events=%s",
            device.device_id,
            payload.uptime_ms,
            payload.sensors.distance_cm,
            payload.emitter.active,
            payload.robot.state.value,
            ",".join(row.event_type for row in created),
        )
    else:
        logger.debug("device=%s telemetry uptime_ms=%s", device.device_id, payload.uptime_ms)

    return IngestResult(
        device=device,
        created_events=created,
        duplicates=[],
        sample_written=sample_written,
    )


def ingest_event_batch(
    session: Session,
    batch: EventBatchIn,
    *,
    clock_skew_tolerance_s: int,
) -> EventIngestResult:
    now = utcnow()
    presence = device_service.register_presence(session, batch.device_id, now=now)
    device = presence.device

    created: list[Event] = []
    duplicates: list[Event] = []

    if presence.became_online:
        created.append(
            _record(
                session,
                device,
                EventDraft(
                    event_type=EventType.DEVICE_ONLINE,
                    occurred_at=now,
                    metadata={"reason": "first_contact" if presence.is_new else "reconnected"},
                    source=TelemetrySource.SERVER,
                ),
                received_at=now,
            ).row
        )

    for item in batch.events:
        draft, rejected = _draft_from_event(item, now, clock_skew_tolerance_s)
        recorded = _record(session, device, draft, received_at=now, timestamp_rejected=rejected)
        (duplicates if recorded.duplicate else created).append(recorded.row)

    session.commit()
    session.refresh(device)

    if created:
        logger.info(
            "device=%s events ingested types=%s",
            device.device_id,
            ",".join(row.event_type for row in created),
        )

    return EventIngestResult(device=device, created_events=created, duplicates=duplicates)


def mark_devices_offline(session: Session, timeout_s: float) -> list[Event]:
    """Expire devices whose heartbeat lapsed. Returns the DEVICE_OFFLINE events created."""
    now = utcnow()
    expired = device_service.expired_device_ids(session, now, timeout_s)
    created: list[Event] = []
    for device_id in expired:
        device = device_service.mark_offline(session, device_id, now=now)
        if device is None:
            continue
        recorded = _record(
            session,
            device,
            EventDraft(
                event_type=EventType.DEVICE_OFFLINE,
                occurred_at=now,
                distance_cm=device.distance_cm,
                vibration=bool(device.vibration),
                ir_detected=bool(device.ir_detected),
                emitter_active=bool(device.emitter_active),
                robot_state=device.robot_state,
                source=TelemetrySource.SERVER,
                metadata={
                    "last_seen_at": device.last_seen_at.isoformat() + "Z",
                    "timeout_s": timeout_s,
                    "emitter_active_at_disconnect": bool(device.emitter_active),
                },
            ),
            received_at=now,
        )
        created.append(recorded.row)
        logger.warning("device=%s marked OFFLINE last_seen=%s", device_id, device.last_seen_at)

    if created:
        session.commit()
    return created


def _record(
    session: Session,
    device: Device,
    draft: EventDraft,
    *,
    received_at: datetime,
    timestamp_rejected: bool = False,
) -> RecordedEvent:
    return event_service.record_event(
        session,
        device,
        draft,
        received_at=received_at,
        device_timestamp_rejected=timestamp_rejected,
    )


def _draft_from_event(
    item: EventIn, received_at: datetime, clock_skew_tolerance_s: int
) -> tuple[EventDraft, bool]:
    occurred_at, rejected = resolve_event_time(
        item.parsed_timestamp(), received_at, clock_skew_tolerance_s
    )
    metadata = dict(item.metadata or {})
    if rejected:
        metadata["device_timestamp_rejected"] = True
    if item.uptime_ms is not None:
        metadata.setdefault("uptime_ms", item.uptime_ms)

    return (
        EventDraft(
            event_type=item.type,
            occurred_at=occurred_at,
            distance_cm=item.distance_cm,
            vibration=item.vibration,
            ir_detected=item.ir_detected,
            emitter_active=item.emitter_active,
            robot_state=item.robot_state.value if item.robot_state else None,
            message=item.message,
            detail=item.detail,
            metadata=metadata,
            source=TelemetrySource.DEVICE,
        ),
        rejected,
    )


def _reconcile_drafts(
    *,
    previous_emitter: bool,
    previous_robot_state: RobotState,
    emitter_active: bool,
    robot_state: RobotState,
    context: _EventContext,
) -> list[EventDraft]:
    drafts: list[EventDraft] = []

    if emitter_active != previous_emitter:
        drafts.append(
            _transition_draft(
                event_type=(
                    EventType.EMITTER_ACTIVATED if emitter_active else EventType.EMITTER_DEACTIVATED
                ),
                reason="emitter_state_transition",
                context=context,
            )
        )

    was_moving = previous_robot_state in MOVING_STATES
    is_moving = robot_state in MOVING_STATES
    if is_moving != was_moving:
        drafts.append(
            _transition_draft(
                event_type=EventType.ROBOT_MOVING if is_moving else EventType.ROBOT_STOPPED,
                reason="robot_state_transition",
                context=context,
            )
        )

    return drafts


def _transition_draft(*, event_type: EventType, reason: str, context: _EventContext) -> EventDraft:
    return EventDraft(
        event_type=event_type,
        occurred_at=context.received_at,
        distance_cm=context.distance_cm,
        vibration=context.vibration,
        ir_detected=context.ir_detected,
        emitter_active=context.emitter_active,
        robot_state=context.robot_state,
        metadata={"derived": reason},
        source=TelemetrySource.SERVER,
    )
