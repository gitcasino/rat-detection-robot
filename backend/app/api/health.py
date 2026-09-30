"""Service health."""

from __future__ import annotations

import logging
from time import monotonic

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import session_dep
from app.schemas import HealthOut
from app.services import devices as device_service
from app.timeutils import as_utc, utcnow
from app.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

STARTED_AT = monotonic()
VERSION = "1.0.0"


@router.get("/health", response_model=HealthOut, summary="Liveness and dependency check")
def health(session: Session = Depends(session_dep)) -> HealthOut:
    database_ok = True
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("database health check failed")
        database_ok = False

    online = 0
    total = 0
    if database_ok:
        total = len(device_service.list_devices(session))
        online = device_service.count_online(session)

    return HealthOut(
        status="ok" if database_ok else "degraded",
        version=VERSION,
        uptime_seconds=round(monotonic() - STARTED_AT, 3),
        database="ok" if database_ok else "error",
        server_time=as_utc(utcnow()),
        devices=total,
        devices_online=online,
        websocket_clients=manager.client_count,
    )


@router.get("/health/ready", response_model=HealthOut, include_in_schema=False)
def readiness(session: Session = Depends(session_dep)) -> HealthOut:
    return health(session)
