"""History and event detail endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import session_dep, settings_dep
from app.domain import EventCategory, EventType
from app.models import Event
from app.schemas import EmitterSessionOut, EventOut, EventPage
from app.services import events as event_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["history"])


@router.get("/events", response_model=EventPage, summary="Query the chronological event log")
def list_events(
    device_id: str | None = Query(default=None, max_length=64),
    type: list[EventType] | None = Query(default=None),
    category: list[EventCategory] | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(settings_dep),
) -> EventPage:
    limit = min(limit, settings.history_max_limit)
    rows, total = event_service.query_events(
        session,
        device_id=device_id,
        event_types=type,
        categories=category,
        search=search,
        since=since,
        until=until,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )
    return EventPage(
        items=[EventOut.from_model(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=EventOut, summary="Fetch one event")
def get_event(event_id: int, session: Session = Depends(session_dep)) -> EventOut:
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventOut.from_model(row)


@router.get(
    "/devices/{device_id}/emitter-sessions",
    response_model=list[EmitterSessionOut],
    summary="Emitter activation windows with measured durations",
)
def list_emitter_sessions(
    device_id: str,
    limit: int = Query(default=25, ge=1, le=200),
    session: Session = Depends(session_dep),
) -> list[EmitterSessionOut]:
    rows = event_service.emitter_sessions(session, device_id=device_id, limit=limit)
    return [EmitterSessionOut.model_validate(row, from_attributes=True) for row in rows]
