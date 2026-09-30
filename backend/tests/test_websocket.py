"""Live WebSocket fan-out."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import stream as stream_api
from tests.conftest import DEVICE_ID, telemetry_payload


def _drain_until(websocket, wanted: str, limit: int = 8) -> dict:
    for _ in range(limit):
        frame = websocket.receive_json()
        if frame.get("type") == wanted:
            return frame
    raise AssertionError(f"frame {wanted!r} not received")


def test_snapshot_is_sent_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        snapshot = websocket.receive_json()

    assert snapshot["type"] == "snapshot"
    assert snapshot["devices"] == []
    assert snapshot["events"] == []
    assert snapshot["backend"]["backend"] == "online"


def test_snapshot_contains_existing_state_and_history(client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    with client.websocket_connect("/ws") as websocket:
        snapshot = websocket.receive_json()

    assert len(snapshot["devices"]) == 1
    assert snapshot["devices"][0]["device_id"] == DEVICE_ID
    assert len(snapshot["events"]) == 1
    assert snapshot["events"][0]["event_type"] == "DEVICE_ONLINE"


def test_telemetry_post_broadcasts_state_and_events(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # snapshot

        client.post("/api/telemetry", json=telemetry_payload(emitter={"active": True}))

        telemetry_frame = _drain_until(websocket, "telemetry")
        event_frame = _drain_until(websocket, "events")

    assert telemetry_frame["device"]["emitter_active"] is True
    assert telemetry_frame["device"]["robot_state"] == "MONITORING"
    assert event_frame["device_id"] == DEVICE_ID
    assert "EMITTER_ACTIVATED" in [event["event_type"] for event in event_frame["events"]]


def test_event_batch_broadcasts_new_events(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        client.post(
            "/api/events",
            json={
                "device_id": DEVICE_ID,
                "events": [{"type": "VIBRATION_DETECTED", "vibration": True}],
            },
        )

        events_frame = _drain_until(websocket, "events")

    types = [event["event_type"] for event in events_frame["events"]]
    assert types == ["DEVICE_ONLINE", "VIBRATION_DETECTED"]


def test_keepalive_pong_is_emitted(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(stream_api, "KEEPALIVE_INTERVAL_S", 0.01)

    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # snapshot
        pong = _drain_until(websocket, "pong")

    assert pong["type"] == "pong"


def test_client_ping_is_answered_promptly(client: TestClient, monkeypatch) -> None:
    """A ping must not wait for the idle keepalive timer to expire."""
    monkeypatch.setattr(stream_api, "KEEPALIVE_INTERVAL_S", 30.0)

    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # snapshot
        websocket.send_json({"type": "ping"})
        frame = websocket.receive_json()

    assert frame["type"] == "pong"
    assert frame["server_time"].endswith("Z")


def test_unknown_client_frames_are_ignored(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # snapshot
        websocket.send_json({"type": "launch_the_emitter"})
        websocket.send_text("not json at all")
        websocket.send_json({"type": "ping"})

        frame = websocket.receive_json()

    assert frame["type"] == "pong"


def test_status_endpoint_reports_websocket_clients(client: TestClient) -> None:
    assert client.get("/api/status").json()["backend"]["websocket"] == "disconnected"

    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()
        assert client.get("/api/status").json()["backend"]["websocket"] == "connected"
        assert client.get("/api/status").json()["backend"]["websocket_clients"] >= 1


def test_device_scoped_socket_still_receives_frames(client: TestClient) -> None:
    with client.websocket_connect(f"/ws?device_id={DEVICE_ID}") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["device_filter"] == DEVICE_ID
