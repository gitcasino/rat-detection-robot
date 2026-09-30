"""Aggregate statistics derived from the event history."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import CATEGORY_BY_EVENT_TYPE, EventType
from app.models import Device, EmitterSession, Event
from app.schemas import EmitterSessionOut, StatBucket, StatsOut
from app.services import devices as device_service
from app.timeutils import as_utc, utcnow

DEFAULT_WINDOW_HOURS = 24
BUCKET_MINUTES = 60


def compute_stats(
    session: Session,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    buckets: int = 24,
) -> StatsOut:
    now = utcnow()
    window_start = now - timedelta(hours=window_hours)

    total_events = session.scalar(select(func.count()).select_from(Event)) or 0

    type_rows = session.execute(
        select(Event.event_type, func.count())
        .where(Event.received_at >= window_start)
        .group_by(Event.event_type)
    ).all()
    by_type = {row[0]: int(row[1]) for row in type_rows}
    by_category = Counter()
    for event_type, count in by_type.items():
        member = EventType(event_type) if event_type in EventType._value2member_map_ else None
        if member is None:  # pragma: no cover - forward compatibility
            continue
        by_category[CATEGORY_BY_EVENT_TYPE[member].value] += count

    events_in_window = sum(by_type.values())

    durations = session.execute(
        select(EmitterSession.duration_seconds).where(EmitterSession.duration_seconds.isnot(None))
    ).scalars().all()
    closed_durations = [float(value) for value in durations]

    activation_count = by_type.get(EventType.EMITTER_ACTIVATED.value, 0)
    total_active = session.scalar(select(func.sum(EmitterSession.duration_seconds))) or 0.0
    total_active = float(total_active)

    open_sessions = list(
        session.scalars(select(EmitterSession).where(EmitterSession.deactivated_at.is_(None)))
    )

    bucket_width = timedelta(minutes=BUCKET_MINUTES)
    timeline: list[StatBucket] = []
    if buckets > 0:
        anchor = now.replace(second=0, microsecond=0)
        start = anchor - bucket_width * (buckets - 1)
        rows = session.execute(
            select(Event.received_at)
            .where(Event.received_at >= start)
            .order_by(Event.received_at)
        ).scalars().all()
        cursor = start
        index = 0
        ordered = [as_utc(value) for value in rows if value is not None]
        for step in range(buckets):
            edge = cursor + bucket_width
            count = 0
            while index < len(ordered) and ordered[index] < as_utc(edge):
                count += 1
                index += 1
            timeline.append(StatBucket(bucket=as_utc(cursor), count=count))
            cursor = edge

    device_states = session.execute(
        select(Device.state, func.count()).group_by(Device.state)
    ).all()

    last_event_at = session.scalar(select(func.max(Event.received_at)))

    average = round(total_active / len(closed_durations), 3) if closed_durations else None
    longest = round(max(closed_durations), 3) if closed_durations else None

    return StatsOut(
        generated_at=as_utc(now),
        window_hours=window_hours,
        total_events=total_events,
        events_in_window=events_in_window,
        events_by_type=dict(sorted(by_type.items())),
        events_by_category=dict(by_category),
        emitter_activations=activation_count,
        emitter_active_seconds=round(total_active, 3),
        emitter_average_seconds=average,
        emitter_longest_seconds=longest,
        emitter_open_session=(
            EmitterSessionOut.model_validate(open_sessions[0], from_attributes=True)
            if open_sessions
            else None
        ),
        events_per_bucket=timeline,
        devices_by_state={row[0]: int(row[1]) for row in device_states},
        last_event_at=as_utc(last_event_at),
    )
