"""Statistics aggregation over real history only."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import DEVICE_ID, telemetry_payload


def test_stats_on_an_empty_database_are_zeroed(client: TestClient) -> None:
    stats = client.get("/api/stats").json()

    assert stats["total_events"] == 0
    assert stats["events_in_window"] == 0
    assert stats["events_by_type"] == {}
    assert stats["emitter_activations"] == 0
    assert stats["emitter_active_seconds"] == 0
    assert stats["emitter_average_seconds"] is None
    assert stats["emitter_open_session"] is None
    assert stats["last_event_at"] is None
    assert stats["devices_by_state"] == {}
    assert len(stats["events_per_bucket"]) == 24
    assert all(bucket["count"] == 0 for bucket in stats["events_per_bucket"])


def test_stats_count_events_by_type_and_category(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload(emitter={"active": True}))
    client.post("/api/events", json={"device_id": DEVICE_ID, "events": [{"type": "ERROR", "message": "sensor fault"}]})

    stats = client.get("/api/stats").json()

    assert stats["total_events"] >= 3
    assert stats["events_by_type"]["DEVICE_ONLINE"] == 1
    assert stats["events_by_type"]["EMITTER_ACTIVATED"] == 1
    assert stats["events_by_type"]["ERROR"] == 1
    assert stats["events_by_category"]["EMITTER"] == 1
    assert stats["events_by_category"]["ERROR"] == 1
    assert stats["devices_by_state"]["ONLINE"] == 1
    assert stats["last_event_at"] is not None


def test_open_emitter_session_is_reported(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload(emitter={"active": True}))

    stats = client.get("/api/stats").json()

    assert stats["emitter_open_session"] is not None
    assert stats["emitter_open_session"]["deactivated_at"] is None


def test_window_parameter_is_honoured(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    stats = client.get("/api/stats", params={"window_hours": 1}).json()
    assert stats["window_hours"] == 1

    assert client.get("/api/stats", params={"window_hours": 0}).status_code == 422


def test_timeline_buckets_are_chronological(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    buckets = client.get("/api/stats").json()["events_per_bucket"]
    stamps = [bucket["bucket"] for bucket in buckets]

    assert stamps == sorted(stamps)
    assert sum(bucket["count"] for bucket in buckets) >= 1
