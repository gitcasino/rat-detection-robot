"""Timestamp handling.

Two clocks are in play and they are never conflated:

* the device clock (NTP synchronised on the ESP32, may be unset or wrong),
* the server clock, which is authoritative for persisted history.

SQLite has no native timezone support, so everything is stored as naive UTC and
re-tagged as UTC at the API boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_aware(value: datetime) -> bool:
    return value.tzinfo is not None


def strip_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_device_timestamp(value: object) -> datetime | None:
    """Accept ISO-8601 strings or epoch seconds/milliseconds from the firmware.

    Returns a naive UTC datetime, or None when the value is unusable.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
        # Anything below ~1e11 cannot be milliseconds for a plausible build year
        # and is therefore interpreted as seconds.
        seconds = numeric / 1000.0 if numeric > 1e11 else numeric
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_device_timestamp(int(text))
        normalised = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalised)
        except ValueError:
            return None
        return strip_tz(parsed)

    return None


def elapsed_ms(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() * 1000.0)
