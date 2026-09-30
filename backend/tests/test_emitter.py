"""Emitter state machine as observed through the API.

The emitter panel is the feature the project is judged on, so activation,
deactivation, duration accounting and de-duplication are covered explicitly.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from tests.conftest import DEVICE_ID, telemetry_payload


def _emitter_payload(active: bool, **overrides):
    payload = telemetry_payload(emitter={"active": active, "mode": "ULTRASONIC_PULSE"})
    payload["robot"] = {"state": "EMITTER_ACTIVE" if active else "MONITORING"}
    payload.update(overrides)
    return payload


def test_activation_is_recorded_once_per_transition(client: TestClient) -> None:
    client.post("/api/telemetry", json=_emitter_payload(False))

    first = client.post("/api/telemetry", json=_emitter_payload(True))
    second = client.post("/api/telemetry", json=_emitter_payload(True))
    third = client.post("/api/telemetry", json=_emitter_payload(True))

    assert [event["event_type"] for event in first.json()["events"]] == ["EMITTER_ACTIVATED"]
    assert second.json()["events"] == []
    assert third.json()["events"] == []

    activations = client.get("/api/events", params={"type": "EMITTER_ACTIVATED"}).json()
    assert activations["total"] == 1

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["emitter_active"] is True
    assert device["emitter_activations"] == 1
    assert device["open_session"] is not None


def test_deactivation_closes_the_session_with_a_measured_duration(client: TestClient) -> None:
    client.post("/api/telemetry", json=_emitter_payload(False))
    client.post("/api/telemetry", json=_emitter_payload(True))

    time.sleep(0.05)

    response = client.post("/api/telemetry", json=_emitter_payload(False))
    event_types = [event["event_type"] for event in response.json()["events"]]
    assert "EMITTER_DEACTIVATED" in event_types

    history = client.get("/api/events", params={"type": "EMITTER_DEACTIVATED"}).json()
    deactivation = history["items"][0]
    duration = deactivation["emitter_duration_seconds"]
    assert duration is not None
    assert 0.0 < duration < 60.0

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["emitter_active"] is False
    assert device["emitter_activated_at"] is None
    assert device["emitter_active_seconds"] == pytest.approx(duration, abs=0.005)
    assert device["open_session"] is None

    sessions = client.get(f"/api/devices/{DEVICE_ID}/emitter-sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["duration_seconds"] == pytest.approx(duration, abs=0.005)
    assert sessions[0]["deactivated_at"] is not None


def test_multiple_cycles_accumulate_sessions(client: TestClient) -> None:
    for _ in range(2):
        client.post("/api/telemetry", json=_emitter_payload(False))
        client.post("/api/telemetry", json=_emitter_payload(True))
        time.sleep(0.02)
        client.post("/api/telemetry", json=_emitter_payload(False))

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["emitter_activations"] == 2
    assert device["emitter_active_seconds"] > 0

    sessions = client.get(f"/api/devices/{DEVICE_ID}/emitter-sessions").json()
    assert len(sessions) == 2

    stats = client.get("/api/stats").json()
    assert stats["emitter_activations"] >= 2
    assert stats["emitter_active_seconds"] > 0
    assert stats["emitter_average_seconds"] is not None


def test_device_event_confirms_a_server_derived_transition(client: TestClient) -> None:
    """The device's own event and the server reconciliation must not double count."""
    client.post("/api/telemetry", json=_emitter_payload(False))
    client.post("/api/telemetry", json=_emitter_payload(True))

    confirm = client.post(
        "/api/events",
        json={
            "device_id": DEVICE_ID,
            "events": [
                {
                    "type": "EMITTER_ACTIVATED",
                    "distance_cm": 18.2,
                    "emitter_active": True,
                    "robot_state": "EMITTER_ACTIVE",
                    "message": "Emitter command set ACTIVE",
                }
            ],
        },
    )

    assert confirm.status_code == 202
    body = confirm.json()
    assert body["duplicates"] == ["EMITTER_ACTIVATED"]
    assert body["accepted_count"] == 0

    activations = client.get("/api/events", params={"type": "EMITTER_ACTIVATED"}).json()
    assert activations["total"] == 1
    assert activations["items"][0]["metadata"]["confirmed_by_device_event"] is True
    assert activations["items"][0]["source"] == "SERVER"


def test_unpaired_deactivation_does_not_fabricate_a_duration(client: TestClient) -> None:
    response = client.post(
        "/api/events",
        json={
            "device_id": DEVICE_ID,
            "events": [{"type": "EMITTER_DEACTIVATED", "emitter_active": False}],
        },
    )

    assert response.status_code == 202
    event = next(
        item for item in response.json()["events"] if item["event_type"] == "EMITTER_DEACTIVATED"
    )
    assert event["emitter_duration_seconds"] is None
    assert event["metadata"]["unpaired_deactivation"] is True

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["emitter_active_seconds"] == 0


def test_drive_state_transitions_are_recorded(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload(robot={"state": "IDLE"}))
    moving = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "APPROACHING"}))
    idle = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "MONITORING"}))

    assert [event["event_type"] for event in moving.json()["events"]] == ["ROBOT_MOVING"]
    assert [event["event_type"] for event in idle.json()["events"]] == ["ROBOT_STOPPED"]


def test_target_detected_is_a_stationary_state(client: TestClient) -> None:
    """Confirming a target happens in place, so no drive event may be emitted."""
    client.post("/api/telemetry", json=telemetry_payload(robot={"state": "IDLE"}))
    detected = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "TARGET_DETECTED"}))
    approaching = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "APPROACHING"}))
    stopped = client.post("/api/telemetry", json=telemetry_payload(robot={"state": "MONITORING"}))

    assert detected.json()["events"] == []
    assert [event["event_type"] for event in approaching.json()["events"]] == ["ROBOT_MOVING"]
    assert [event["event_type"] for event in stopped.json()["events"]] == ["ROBOT_STOPPED"]
