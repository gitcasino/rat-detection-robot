"""Event persistence, emitter-session bookkeeping and history queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from app.domain import EventCategory, EventType, TelemetrySource
from app.models import Device, EmitterSession, Event, TelemetrySample
from app.services.devices import open_emitter_session
from app.timeutils import utcnow

# Window in which a device-reported event is considered the confirmation of an
# already-derived server event for the same transition.
DEDUPE_WINDOW_S = 2.0

MESSAGE_BY_TYPE: dict[EventType, str] = {
    EventType.DEVICE_ONLINE: "Device registered and reporting telemetry",
    EventType.DEVICE_OFFLINE: "Heartbeat lost, device marked offline",
    EventType.VIBRATION_DETECTED: "Vibration sensor triggered",
    EventType.VIBRATION_CLEARED: "Vibration sensor returned to idle",
    EventType.IR_DETECTED: "IR sensor triggered",
    EventType.IR_CLEARED: "IR sensor returned to idle",
    EventType.DISTANCE_UPDATED: "Distance sample recorded",
    EventType.TARGET_ACTIVITY_DETECTED: "Target activity confirmed by sensor fusion",
    EventType.TARGET_ACTIVITY_CLEARED: "Target activity no longer present",
    EventType.ROBOT_MOVING: "Robot drive engaged",
    EventType.ROBOT_STOPPED: "Robot drive disengaged",
    EventType.EMITTER_ACTIVATED: "Emitter command set ACTIVE",
    EventType.EMITTER_DEACTIVATED: "Emitter command set INACTIVE",
    EventType.OBSTACLE_DETECTED: "Obstacle within clearance threshold",
    EventType.OBSTACLE_CLEARED: "Path ahead clear",
    EventType.ERROR: "Device reported an error condition",
    EventType.HEARTBEAT: "Device heartbeat",
}


@dataclass
class EventDraft:
    """Everything needed to write one row, minus the device bookkeeping."""

    event_type: EventType
    occurred_at: datetime
    distance_cm: float | None = None
    vibration: bool | None = None
    ir_detected: bool | None = None
    emitter_active: bool | None = None
    robot_state: str | None = None
    message: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source: TelemetrySource = TelemetrySource.DEVICE


@dataclass
class RecordedEvent:
    row: Event
    duplicate: bool = False


def default_message(event_type: EventType) -> str:
    return MESSAGE_BY_TYPE.get(event_type, event_type.value)


def record_event(
    session: Session,
    device: Device,
    draft: EventDraft,
    *,
    received_at: datetime | None = None,
    device_timestamp_rejected: bool = False,
) -> RecordedEvent:
    received_at = received_at or utcnow()
    event_type = draft.event_type

    if draft.source is TelemetrySource.DEVICE:
        existing = _recent_reconcile_event(session, device.device_id, event_type, received_at)
        if existing is not None:
            meta = dict(existing.metadata_ or {})
            meta["confirmed_by_device_event"] = True
            existing.metadata_ = meta
            return RecordedEvent(row=existing, duplicate=True)

    row = Event(
        device_id=device.device_id,
        event_type=event_type.value,
        source=draft.source.value,
        occurred_at=draft.occurred_at,
        received_at=received_at,
        device_timestamp_rejected=device_timestamp_rejected,
        distance_cm=draft.distance_cm,
        vibration=draft.vibration,
        ir_detected=draft.ir_detected,
        emitter_active=draft.emitter_active,
        robot_state=draft.robot_state,
        message=draft.message or default_message(event_type),
        detail=draft.detail,
        metadata_=dict(draft.metadata) if draft.metadata else None,
    )
    session.add(row)
    session.flush()

    device.last_event_at = received_at
    _apply_side_effects(session, device, row)
    session.flush()
    return RecordedEvent(row=row)


def _recent_reconcile_event(
    session: Session,
    device_id: str,
    event_type: EventType,
    received_at: datetime,
) -> Event | None:
    candidate = session.scalars(
        select(Event)
        .where(Event.device_id == device_id, Event.event_type == event_type.value)
        .order_by(Event.id.desc())
        .limit(1)
    ).first()
    if candidate is None or candidate.source != TelemetrySource.SERVER.value:
        return None
    if (received_at - candidate.received_at).total_seconds() > DEDUPE_WINDOW_S:
        return None
    return candidate


def _apply_side_effects(session: Session, device: Device, row: Event) -> None:
    """Emitter sessions are the durable record of activation windows.

    Durations are only computed from a matched ACTIVATED/DEACTIVATED pair; an
    unpaired transition records the gap in metadata rather than inventing a value.
    """
    if row.event_type == EventType.EMITTER_ACTIVATED.value:
        stale = open_emitter_session(session, device.device_id)
        if stale is not None:
            stale.deactivated_at = row.occurred_at
            stale.duration_seconds = max(
                0.0, (stale.deactivated_at - stale.activated_at).total_seconds()
            )
        session.add(
            EmitterSession(
                device_id=device.device_id,
                activated_at=row.occurred_at,
                activation_event_id=row.id,
            )
        )
        device.emitter_activated_at = row.occurred_at
        device.emitter_activations = (device.emitter_activations or 0) + 1

    elif row.event_type == EventType.EMITTER_DEACTIVATED.value:
        current = open_emitter_session(session, device.device_id)
        meta = dict(row.metadata_ or {})
        if current is not None:
            current.deactivated_at = row.occurred_at
            current.duration_seconds = max(
                0.0, (current.deactivated_at - current.activated_at).total_seconds()
            )
            current.deactivation_event_id = row.id
            meta["emitter_duration_seconds"] = round(current.duration_seconds, 3)
            meta["emitter_activated_at"] = current.activated_at.isoformat() + "Z"
            device.emitter_active_seconds = (device.emitter_active_seconds or 0.0) + current.duration_seconds
        else:
            meta["emitter_duration_seconds"] = None
            meta["unpaired_deactivation"] = True
        row.metadata_ = meta
        device.emitter_activated_at = None


def history_filter(
    device_id: str | None = None,
    event_types: Sequence[EventType] | None = None,
    categories: Sequence[EventCategory] | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Select:
    stmt = select(Event)

    if device_id:
        stmt = stmt.where(Event.device_id == device_id)
    if event_types:
        stmt = stmt.where(Event.event_type.in_([item.value for item in event_types]))
    if categories:
        from app.domain import CATEGORY_BY_EVENT_TYPE

        allowed = [member.value for member, cat in CATEGORY_BY_EVENT_TYPE.items() if cat in categories]
        stmt = stmt.where(Event.event_type.in_(allowed))
    if search:
        needle = f"%{search.strip().lower()}%"
        conditions = [
            func.lower(Event.event_type).like(needle),
            func.lower(func.coalesce(Event.message, "")).like(needle),
            func.lower(func.coalesce(Event.detail, "")).like(needle),
        ]
        stmt = stmt.where(or_(*conditions))
    if since:
        stmt = stmt.where(Event.received_at >= since)
    if until:
        stmt = stmt.where(Event.received_at <= until)

    return stmt


def query_events(
    session: Session,
    *,
    device_id: str | None = None,
    event_types: Sequence[EventType] | None = None,
    categories: Sequence[EventCategory] | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    descending: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Event], int]:
    base = history_filter(
        device_id=device_id,
        event_types=event_types,
        categories=categories,
        search=search,
        since=since,
        until=until,
    )
    total = session.scalar(
        select(func.count()).select_from(base.order_by(None).subquery())
    ) or 0

    order = Event.received_at.desc() if descending else Event.received_at.asc()
    stmt = base.order_by(order, Event.id.desc() if descending else Event.id.asc())
    rows = list(session.scalars(stmt.limit(limit).offset(offset)))
    return rows, total


def recent_events(session: Session, device_id: str | None, limit: int = 50) -> list[Event]:
    rows, _ = query_events(session, device_id=device_id, limit=limit, descending=True)
    return rows


def emitter_sessions(session: Session, device_id: str | None = None, limit: int = 50) -> list[EmitterSession]:
    stmt = select(EmitterSession).order_by(EmitterSession.activated_at.desc()).limit(limit)
    if device_id:
        stmt = stmt.where(EmitterSession.device_id == device_id)
    return list(session.scalars(stmt))


def iter_types(values: Iterable[str] | None) -> list[EventType]:
    result: list[EventType] = []
    for value in values or ():
        try:
            result.append(EventType(value))
        except ValueError:
            continue
    return result


def purge_old_events(session: Session, retention_days: int) -> int:
    """Explicit retention. Disabled unless `event_retention_days` is greater than zero."""
    if retention_days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=retention_days)
    rows = list(session.scalars(select(Event.id).where(Event.received_at < cutoff)))
    if not rows:
        return 0
    session.execute(delete(Event).where(Event.id.in_(rows)))
    session.execute(delete(TelemetrySample).where(TelemetrySample.received_at < cutoff))
    session.commit()
    return len(rows)
