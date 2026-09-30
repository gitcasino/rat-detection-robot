"""Ingestion endpoints: telemetry frames and device event batches."""

from __future__ import annotations

import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import api_key_guard, session_dep, settings_dep
from app.domain import DeviceState
from app.schemas import EventBatchAck, EventBatchIn, EventOut, TelemetryAck, TelemetryIn
from app.services import realtime
from app.services import telemetry as telemetry_service
from app.timeutils import as_utc, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post(
    "/telemetry",
    response_model=TelemetryAck,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(api_key_guard)],
    summary="Accept one telemetry frame from a robot",
)
async def post_telemetry(
    payload: TelemetryIn,
    session: Session = Depends(session_dep),
    settings: Settings = Depends(settings_dep),
) -> TelemetryAck:
    reject_unknown_device(payload.device_id, settings)

    result = telemetry_service.ingest_telemetry(
        session,
        payload,
        sample_interval_s=settings.telemetry_persist_interval_s,
        clock_skew_tolerance_s=settings.device_clock_skew_tolerance_s,
    )
    await realtime.publish_telemetry(session, result.device, result.created_events)

    return TelemetryAck(
        device_id=result.device.device_id,
        received_at=as_utc(utcnow()),
        server_time_ms=epoch_ms(),
        events=[EventOut.from_model(row) for row in result.created_events],
        device_state=DeviceState(result.device.state),
    )


@router.post(
    "/events",
    response_model=EventBatchAck,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(api_key_guard)],
    summary="Accept a batch of discrete events from a robot",
)
async def post_events(
    payload: EventBatchIn,
    session: Session = Depends(session_dep),
    settings: Settings = Depends(settings_dep),
) -> EventBatchAck:
    reject_unknown_device(payload.device_id, settings)

    result = telemetry_service.ingest_event_batch(
        session,
        payload,
        clock_skew_tolerance_s=settings.device_clock_skew_tolerance_s,
    )
    await realtime.publish_telemetry(session, result.device, result.created_events)

    return EventBatchAck(
        device_id=result.device.device_id,
        received_at=as_utc(utcnow()),
        accepted_count=result.accepted_count,
        duplicates=[row.event_type for row in result.duplicates],
        events=[EventOut.from_model(row) for row in result.created_events],
    )


def epoch_ms() -> int:
    return int(utcnow().replace(tzinfo=timezone.utc).timestamp() * 1000)


def reject_unknown_device(device_id: str, settings: Settings) -> None:
    allowed = settings.allowed_device_id_list
    if allowed and device_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="device_id is not in ALLOWED_DEVICE_IDS",
        )
