"""Test configuration.

The database URL and the timing-sensitive settings are pinned here before any
application module is imported, because `app.config.get_settings` is cached on
first use.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

TEST_DB_PATH = Path(__file__).parent / ".pytest-telemetry.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["DEVICE_OFFLINE_TIMEOUT_S"] = "5"
os.environ["OFFLINE_SCAN_INTERVAL_S"] = "3600"
os.environ["TELEMETRY_PERSIST_INTERVAL_S"] = "0"
os.environ["DEVICE_CLOCK_SKEW_TOLERANCE_S"] = "900"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import Base, get_engine, get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402

DEVICE_ID = "ESP32-TEST"


def pytest_sessionstart(session: pytest.Session) -> None:
    _drop_test_database()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _drop_test_database()


def _drop_test_database() -> None:
    engine = get_engine()
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(TEST_DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()


@pytest.fixture()
def db_ready() -> Iterator[None]:
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def session(db_ready: None) -> Iterator[Session]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def client(db_ready: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@contextmanager
def env_settings(**overrides: str):
    """Temporarily apply environment overrides and rebuild the cached settings."""
    with patch.dict(os.environ, {key: str(value) for key, value in overrides.items()}):
        get_settings.cache_clear()
        try:
            yield get_settings()
        finally:
            get_settings.cache_clear()


def telemetry_payload(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "device_id": DEVICE_ID,
        "uptime_ms": 12_000,
        "emitter": {"active": False},
        "sensors": {"vibration": False, "ir": False, "distance_cm": 42.5},
        "robot": {"state": "MONITORING"},
        "network": {"rssi": -58, "ip": "192.168.1.44", "ssid": "lab-net"},
        "firmware_version": "1.0.0",
    }
    payload.update(overrides)
    return payload
