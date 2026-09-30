"""Health endpoint and service metadata."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]
    assert body["uptime_seconds"] >= 0
    assert body["telemetry_schema_version"] == 1


def test_health_reports_degraded_when_database_is_unavailable(client: TestClient) -> None:
    from app.database import get_db

    def broken_session():
        class _Broken:
            def execute(self, *args, **kwargs):
                raise OperationalError("SELECT 1", {}, Exception("database gone"))

        yield _Broken()

    client.app.dependency_overrides[get_db] = broken_session
    try:
        response = client.get("/api/health")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"


def test_openapi_document_is_served(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in (
        "/api/health",
        "/api/devices",
        "/api/devices/{device_id}",
        "/api/status",
        "/api/events",
        "/api/events/{event_id}",
        "/api/telemetry",
        "/api/stats",
    ):
        assert path in paths
