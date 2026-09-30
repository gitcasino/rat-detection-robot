"""Telemetry ingestion: validation, persistence and edge reconciliation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tests.conftest import DEVICE_ID, env_settings, telemetry_payload


def test_first_telemetry_registers_device(client: TestClient) -> None:
    response = client.post("/api/telemetry", json=telemetry_payload())

    assert response.status_code == 202
    ack = response.json()
    assert ack["accepted"] is True
    assert ack["device_id"] == DEVICE_ID
    assert ack["device_state"] == "ONLINE"
    assert [event["event_type"] for event in ack["events"]] == ["DEVICE_ONLINE"]

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["distance_cm"] == 42.5
    assert device["robot_state"] == "MONITORING"
    assert device["wifi_rssi"] == -58
    assert device["wifi_ssid"] == "lab-net"
    assert device["ip_address"] == "192.168.1.44"
    assert device["uptime_ms"] == 12_000
    assert device["firmware_version"] == "1.0.0"
    assert device["emitter_active"] is False


def test_telemetry_persists_sample_row(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    samples = client.get("/api/stats").json()
    assert samples["total_events"] >= 1
    assert client.get(f"/api/devices/{DEVICE_ID}").json()["last_telemetry_at"] is not None


def test_missing_device_id_is_rejected(client: TestClient) -> None:
    payload = telemetry_payload()
    payload.pop("device_id")

    response = client.post("/api/telemetry", json=payload)

    assert response.status_code == 422


def test_device_id_with_spaces_is_rejected(client: TestClient) -> None:
    response = client.post("/api/telemetry", json=telemetry_payload(device_id="bad id!"))

    assert response.status_code == 422


def test_negative_distance_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/telemetry",
        json=telemetry_payload(sensors={"vibration": False, "ir": False, "distance_cm": -3}),
    )

    assert response.status_code == 422


def test_out_of_range_rssi_is_rejected(client: TestClient) -> None:
    response = client.post("/api/telemetry", json=telemetry_payload(network={"rssi": 12}))

    assert response.status_code == 422


def test_unknown_robot_state_is_rejected(client: TestClient) -> None:
    response = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "DANCING"}))

    assert response.status_code == 422


def test_malformed_json_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/telemetry",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


def test_oversized_payload_is_rejected(client: TestClient) -> None:
    payload = telemetry_payload()
    payload["padding"] = "x" * 200_000

    response = client.post("/api/telemetry", json=payload)

    assert response.status_code == 413


def test_unknown_fields_are_tolerated_for_forward_compatibility(client: TestClient) -> None:
    payload = telemetry_payload()
    payload["future_section"] = {"anything": True}

    response = client.post("/api/telemetry", json=payload)

    assert response.status_code == 202


def test_device_timestamp_is_rejected_when_implausible(client: TestClient) -> None:
    client.post(
        "/api/events",
        json={
            "device_id": DEVICE_ID,
            "events": [{"type": "DISTANCE_UPDATED", "timestamp": "1970-01-01T00:00:10Z", "distance_cm": 30.0}],
        },
    )

    event = client.get("/api/events", params={"type": "DISTANCE_UPDATED"}).json()["items"][0]

    assert event["device_timestamp_rejected"] is True
    assert event["occurred_at"].startswith(str(datetime.now(timezone.utc).year))


def test_device_timestamp_may_be_epoch_milliseconds(client: TestClient) -> None:
    import time

    now_ms = int(time.time() * 1000)

    client.post(
        "/api/events",
        json={"device_id": DEVICE_ID, "events": [{"type": "DISTANCE_UPDATED", "timestamp": now_ms}]},
    )

    event = client.get("/api/events", params={"type": "DISTANCE_UPDATED"}).json()["items"][0]
    assert event["device_timestamp_rejected"] is False


def test_ingestion_is_rejected_for_unlisted_device() -> None:
    with env_settings(ALLOWED_DEVICE_IDS="ESP32-ALLOWED"):
        from app.main import create_app

        with TestClient(create_app()) as guarded:
            blocked = guarded.post("/api/telemetry", json=telemetry_payload())
            allowed = guarded.post(
                "/api/telemetry", json=telemetry_payload(device_id="ESP32-ALLOWED")
            )

    assert blocked.status_code == 403
    assert allowed.status_code == 202


def test_api_key_is_required_when_configured() -> None:
    with env_settings(API_KEYS="super-secret-key"):
        from app.main import create_app

        with TestClient(create_app()) as secured:
            anonymous = secured.post("/api/telemetry", json=telemetry_payload())
            wrong = secured.post(
                "/api/telemetry", json=telemetry_payload(), headers={"X-API-Key": "nope"}
            )
            accepted = secured.post(
                "/api/telemetry",
                json=telemetry_payload(),
                headers={"X-API-Key": "super-secret-key"},
            )

    assert anonymous.status_code == 401
    assert wrong.status_code == 403
    assert accepted.status_code == 202


def test_history_is_not_seeded_with_demo_data(client: TestClient) -> None:
    """The production database must start empty; nothing fabricates history."""
    empty = client.get("/api/events").json()
    assert empty == {"items": [], "total": 0, "limit": 100, "offset": 0}

    devices = client.get("/api/devices").json()
    assert devices == []

    status = client.get("/api/status").json()
    assert status["device_count"] == 0
    assert status["devices"] == []


def test_json_payload_round_trip_preserves_unknown_keys(client: TestClient) -> None:
    body = json.dumps(telemetry_payload()).encode()
    response = client.post(
        "/api/telemetry", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 202
