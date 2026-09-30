"""Heartbeat expiry, reconnect handling and the OFFLINE projection."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain import DeviceState
from app.services import telemetry as telemetry_service
from app.timeutils import utcnow
from tests.conftest import DEVICE_ID, telemetry_payload


def test_device_is_marked_offline_after_the_timeout(session: Session, client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    assert client.get(f"/api/devices/{DEVICE_ID}").json()["state"] == "ONLINE"

    created = telemetry_service.mark_devices_offline(session, timeout_s=0)

    assert [row.event_type for row in created] == ["DEVICE_OFFLINE"]

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["state"] == "OFFLINE"
    assert device["offline_since"] is not None
    assert device["offline_count"] == 1

    offline_events = client.get("/api/events", params={"type": "DEVICE_OFFLINE"}).json()
    assert offline_events["total"] == 1
    assert offline_events["items"][0]["metadata"]["timeout_s"] == 0

    status = client.get("/api/status").json()
    assert status["devices_offline"] == 1
    assert status["devices_online"] == 0


def test_offline_scan_is_idempotent(session: Session, client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    first = telemetry_service.mark_devices_offline(session, timeout_s=0)
    second = telemetry_service.mark_devices_offline(session, timeout_s=0)

    assert len(first) == 1
    assert second == []
    assert client.get("/api/events", params={"type": "DEVICE_OFFLINE"}).json()["total"] == 1


def test_offline_scan_respects_the_configured_timeout(session: Session, client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    assert telemetry_service.mark_devices_offline(session, timeout_s=3600) == []


def test_expired_devices_are_found_by_last_seen(session: Session, client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())

    from app.models import Device

    row = session.get(Device, DEVICE_ID)
    row.last_seen_at = utcnow() - timedelta(minutes=5)
    session.commit()

    created = telemetry_service.mark_devices_offline(session, timeout_s=60)
    assert [event.device_id for event in created] == [DEVICE_ID]


def test_reconnect_records_a_new_online_event(session: Session, client: TestClient) -> None:
    client.post("/api/telemetry", json=telemetry_payload())
    telemetry_service.mark_devices_offline(session, timeout_s=0)

    reconnected = client.post("/api/telemetry", json=telemetry_payload(uptime_ms=999_999))

    assert reconnected.status_code == 202
    types = [event["event_type"] for event in reconnected.json()["events"]]
    assert types == ["DEVICE_ONLINE"]

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["state"] == "ONLINE"
    assert device["offline_since"] is None

    online_events = client.get("/api/events", params={"type": "DEVICE_ONLINE"}).json()
    assert online_events["total"] == 2
    assert online_events["items"][0]["metadata"]["reason"] == "reconnected"


def test_offline_state_is_reported_even_while_the_emitter_was_active(
    session: Session, client: TestClient
) -> None:
    client.post("/api/telemetry", json=telemetry_payload(emitter={"active": True}))
    telemetry_service.mark_devices_offline(session, timeout_s=0)

    device = client.get(f"/api/devices/{DEVICE_ID}").json()
    assert device["state"] == "OFFLINE"
    assert device["emitter_active"] is True

    offline_event = client.get("/api/events", params={"type": "DEVICE_OFFLINE"}).json()["items"][0]
    assert offline_event["emitter_active"] is True
    assert offline_event["metadata"]["emitter_active_at_disconnect"] is True


def test_unknown_device_returns_404(client: TestClient) -> None:
    assert client.get("/api/devices/NOPE").status_code == 404


def test_device_state_enum_is_explicit(session: Session) -> None:
    assert {member.value for member in DeviceState} == {"ONLINE", "OFFLINE"}
