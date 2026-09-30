"""Device event ingestion, history queries and filtering."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import DEVICE_ID, telemetry_payload


def _batch(*events: dict) -> dict:
    return {"schema_version": 1, "device_id": DEVICE_ID, "events": list(events)}


def test_sensor_events_are_persisted(client: TestClient) -> None:
    response = client.post(
        "/api/events",
        json=_batch(
            {
                "type": "VIBRATION_DETECTED",
                "distance_cm": 24.4,
                "vibration": True,
                "ir_detected": False,
                "robot_state": "MONITORING",
                "message": "Surface vibration above threshold",
                "metadata": {"axis": "surface", "amplitude": "high"},
            },
            {"type": "IR_DETECTED", "ir_detected": True},
            {"type": "TARGET_ACTIVITY_DETECTED", "vibration": True, "ir_detected": True},
            {"type": "OBSTACLE_DETECTED", "distance_cm": 12.0},
        ),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_count"] == 4
    types = [event["event_type"] for event in body["events"]]
    assert types == [
        "DEVICE_ONLINE",
        "VIBRATION_DETECTED",
        "IR_DETECTED",
        "TARGET_ACTIVITY_DETECTED",
        "OBSTACLE_DETECTED",
    ]
    assert body["accepted_count"] == 4

    vibration = next(
        event for event in body["events"] if event["event_type"] == "VIBRATION_DETECTED"
    )
    assert vibration["distance_cm"] == 24.4
    assert vibration["vibration"] is True
    assert vibration["metadata"]["axis"] == "surface"
    assert vibration["category"] == "SENSORS"
    assert vibration["source"] == "DEVICE"


def test_obstacle_events_are_not_labelled_as_rat_detection(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload(sensors={"distance_cm": 8.0, "vibration": False, "ir": False}))
    client.post("/api/events", json=_batch({"type": "OBSTACLE_DETECTED", "distance_cm": 8.0}))

    history = client.get("/api/events").json()
    assert history["total"] == 2
    assert all(event["event_type"] != "TARGET_ACTIVITY_DETECTED" for event in history["items"])


def test_unknown_event_type_is_rejected(client: TestClient) -> None:
    response = client.post("/api/events", json=_batch({"type": "RAT_SPOTTED"}))

    assert response.status_code == 422


def test_empty_batch_is_rejected(client: TestClient) -> None:
    response = client.post("/api/events", json={"device_id": DEVICE_ID, "events": []})

    assert response.status_code == 422


def test_error_events_are_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/events",
        json=_batch(
            {
                "type": "ERROR",
                "message": "Ultrasonic read out of range",
                "detail": "echo pulse missing for 5 consecutive samples",
                "metadata": {"module": "sensors"},
            }
        ),
    )

    assert response.status_code == 202
    event = next(
        item for item in response.json()["events"] if item["event_type"] == "ERROR"
    )
    assert event["category"] == "ERROR"


def test_history_supports_filters_sorting_and_pagination(client: TestClient) -> None:
    client.post("/api/events", json=_batch({"type": "VIBRATION_DETECTED"}, {"type": "IR_DETECTED"}))
    client.post("/api/events", json=_batch({"type": "VIBRATION_CLEARED"}, {"type": "IR_CLEARED"}))
    client.post("/api/events", json=_batch({"type": "ROBOT_MOVING"}))

    everything = client.get("/api/events").json()
    assert everything["total"] == 6

    emitters = client.get("/api/events", params={"category": "EMITTER"}).json()
    assert emitters["total"] == 0

    robot = client.get("/api/events", params={"category": "ROBOT"}).json()
    assert robot["total"] == 1

    typed = client.get("/api/events", params={"type": ["VIBRATION_DETECTED", "IR_DETECTED"]}).json()
    assert typed["total"] == 2

    searched = client.get("/api/events", params={"search": "vibration"}).json()
    assert searched["total"] == 2

    ascending = client.get("/api/events", params={"order": "asc"}).json()
    assert [event["event_type"] for event in ascending["items"]][0] == "DEVICE_ONLINE"

    page = client.get("/api/events", params={"limit": 2, "offset": 1}).json()
    assert len(page["items"]) == 2
    assert page["offset"] == 1
    assert page["total"] == 6


def test_history_is_scoped_to_a_device(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())
    client.post("/api/telemetry", json=telemetry_payload(device_id="ESP32-OTHER"))

    scoped = client.get("/api/events", params={"device_id": "ESP32-OTHER"}).json()
    assert scoped["total"] == 1
    assert scoped["items"][0]["device_id"] == "ESP32-OTHER"


def test_event_detail_and_missing_event(client: TestClient) -> None:
    client.post("/api/events", json=_batch({"type": "VIBRATION_DETECTED", "message": "Knock detected"}))

    listed = client.get("/api/events").json()["items"]
    event_id = listed[0]["id"]

    detail = client.get(f"/api/events/{event_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == event_id

    assert client.get("/api/events/999999").status_code == 404


def test_clearing_filters_does_not_delete_history(client: TestClient) -> None:
    client.post("/api/events", json=_batch({"type": "VIBRATION_DETECTED"}))

    filtered = client.get("/api/events", params={"category": "ERROR"}).json()
    assert filtered["total"] == 0

    full = client.get("/api/events").json()
    assert full["total"] == 2
