"""FastAPI application factory and process lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import devices as devices_api
from app.api import events as events_api
from app.api import health as health_api
from app.api import stream as stream_api
from app.api import telemetry as telemetry_api
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.middleware import PayloadLimitMiddleware
from app.services import devices as device_service
from app.services import events as event_service
from app.services import realtime
from app.services import telemetry as telemetry_service
from app.websocket import manager

logger = logging.getLogger("app")

DESCRIPTION = """
Telemetry ingest and event-history backend for the Smart Rat Detection and
Repellent Robot.

The ESP32 is the only source of physical telemetry. This service validates,
persists and redistributes what the robot reports; it never synthesises sensor
readings or emitter transitions.
""".strip()

API_PREFIX = "/api"


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_db()
    logger.info(
        "database ready url=%s offline_timeout_s=%s sample_interval_s=%s",
        settings.database_url,
        settings.device_offline_timeout_s,
        settings.telemetry_persist_interval_s,
    )
    app.state.offline_task = asyncio.create_task(_offline_monitor())
    logger.info("offline monitor started interval_s=%s", settings.offline_scan_interval_s)
    try:
        yield
    finally:
        task = getattr(app.state, "offline_task", None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await manager.shutdown()
        logger.info("shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Smart Rat Detection and Repellent Robot - Telemetry Backend",
        description=DESCRIPTION,
        version=health_api.VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(PayloadLimitMiddleware, max_bytes=settings.max_payload_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
        max_age=600,
    )

    app.include_router(health_api.router, prefix=API_PREFIX)
    app.include_router(devices_api.router, prefix=API_PREFIX)
    app.include_router(events_api.router, prefix=API_PREFIX)
    app.include_router(telemetry_api.router, prefix=API_PREFIX)
    app.include_router(stream_api.router)

    return app


async def _offline_monitor() -> None:
    """Heartbeat expiry loop.

    Runs in-process; a single backend instance is the documented topology, so no
    distributed coordination is required. A missed tick only delays the OFFLINE
    transition.
    """
    settings = get_settings()
    session_factory = get_session_factory()

    while True:
        try:
            await asyncio.sleep(settings.offline_scan_interval_s)
            session = session_factory()
            try:
                created = telemetry_service.mark_devices_offline(
                    session, settings.device_offline_timeout_s
                )
                for device_id in sorted({row.device_id for row in created}):
                    device = device_service.get_device(session, device_id)
                    if device is not None:
                        await realtime.broadcast_device_state(session, device)
                purged = event_service.purge_old_events(session, settings.event_retention_days)
                if purged:
                    logger.info("retention purged %s events older than %s days", purged, settings.event_retention_days)
            finally:
                session.close()
        except asyncio.CancelledError:
            logger.info("offline monitor stopped")
            raise
        except Exception:  # pragma: no cover - keep the monitor alive
            logger.exception("offline monitor tick failed")


app = create_app()
