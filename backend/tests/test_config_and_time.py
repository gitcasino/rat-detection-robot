"""Configuration parsing and clock-trust rules."""

from __future__ import annotations

from datetime import timedelta

from app.config import Settings
from app.services.telemetry import resolve_event_time
from app.timeutils import parse_device_timestamp, utcnow


def test_cors_origins_are_split() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test ,")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_api_keys_and_device_allow_list_are_split() -> None:
    settings = Settings(api_keys="a,b , c", allowed_device_ids="ESP32-01,ESP32-02")
    assert settings.api_key_list == ["a", "b", "c"]
    assert settings.allowed_device_id_list == ["ESP32-01", "ESP32-02"]


def test_retention_is_disabled_by_default() -> None:
    assert Settings().event_retention_days == 0


def test_iso_timestamp_is_parsed() -> None:
    parsed = parse_device_timestamp("2026-09-30T12:43:21.284Z")
    assert parsed is not None
    assert parsed.year == 2026 and parsed.microsecond == 284000


def test_epoch_milliseconds_and_seconds_are_parsed() -> None:
    millis = parse_device_timestamp(1_757_000_000_000)
    seconds = parse_device_timestamp(1_757_000_000)
    assert millis == seconds


def test_garbage_timestamp_returns_none() -> None:
    assert parse_device_timestamp("not-a-time") is None
    assert parse_device_timestamp(None) is None
    assert parse_device_timestamp(True) is None
    assert parse_device_timestamp({"at": "now"}) is None


def test_device_clock_is_rejected_when_far_from_server() -> None:
    now = utcnow()

    accepted, rejected = resolve_event_time(now, now, 900)
    assert accepted == now and rejected is False

    stale, rejected = resolve_event_time(now - timedelta(hours=3), now, 900)
    assert stale == now and rejected is True

    missing, rejected = resolve_event_time(None, now, 900)
    assert missing == now and rejected is True


def test_epoch_zero_device_clock_falls_back_to_server_time() -> None:
    now = utcnow()
    epoch_zero = parse_device_timestamp(0)

    resolved, rejected = resolve_event_time(epoch_zero, now, 900)

    assert resolved == now
    assert rejected is True
