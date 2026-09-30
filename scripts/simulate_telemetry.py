#!/usr/bin/env python3
"""Development-only telemetry simulator.

IMPORTANT: this script fabricates telemetry. It exists so a developer can see the
console populated without a robot on the bench, and for that reason it is opt-in
twice over:

  * it refuses to run unless --confirm-synthetic is passed;
  * it refuses to talk to anything but localhost unless --allow-remote is passed.

Never point it at a database you care about: the events it posts are
indistinguishable from real ones once stored. Real device telemetry is the only
supported source of production data.

Usage:
    make backend
    python scripts/simulate_telemetry.py --confirm-synthetic
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post(url: str, payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - localhost by default
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def get(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - localhost by default
        return json.loads(response.read().decode("utf-8"))


class Scenario:
    """A rough approximation of a patrol: idle, activity, approach, repel."""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.tick = 0

    def next_payload(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        self.tick += 1
        cycle = self.tick % 40
        distance = round(random.uniform(60.0, 150.0), 1)
        robot_state = "IDLE"
        vibration = False
        infrared = False
        emitter = False
        events: list[dict[str, Any]] = []

        if 8 <= cycle < 14:
            distance = round(random.uniform(10.0, 19.0), 1)
            vibration = True
            infrared = cycle % 2 == 0
            robot_state = "TARGET_DETECTED"
            if cycle == 8:
                events.append(
                    {
                        "type": "TARGET_ACTIVITY_DETECTED",
                        "message": "Simulated sensor fusion confirmation",
                        "distance_cm": distance,
                    }
                )
        elif 14 <= cycle < 20:
            distance = round(random.uniform(12.0, 30.0), 1)
            robot_state = "APPROACHING"
        elif 20 <= cycle < 26:
            robot_state = "EMITTER_ACTIVE"
            emitter = True
        elif 26 <= cycle < 30:
            robot_state = "MONITORING"
        elif 30 <= cycle < 34:
            distance = round(random.uniform(0.0, 14.0), 1)
            robot_state = "OBSTACLE_AVOIDANCE"
            if cycle == 30:
                events.append({"type": "OBSTACLE_DETECTED", "message": "Simulated obstacle", "distance_cm": distance})
        elif cycle == 34:
            robot_state = "MONITORING"
            events.append({"type": "TARGET_ACTIVITY_CLEARED", "message": "Simulated activity gone"})

        if cycle == 20:
            events.append({"type": "EMITTER_ACTIVATED", "message": "Simulated emitter command"})

        telemetry = {
            "schema_version": 1,
            "device_id": self.device_id,
            "timestamp": now_iso(),
            "uptime_ms": self.tick * 1000,
            "emitter": {"active": emitter, "mode": "BURST", "commanded_by": "simulator"},
            "sensors": {
                "vibration": vibration,
                "ir_detected": infrared,
                "distance_cm": distance,
                "distance_valid": True,
            },
            "robot": {
                "state": robot_state,
                "left_motor": 40 if robot_state == "APPROACHING" else 0,
                "right_motor": 40 if robot_state == "APPROACHING" else 0,
                "obstacle_distance_cm": distance,
            },
            "network": {"rssi": random.randint(-72, -48), "ip": "127.0.0.1", "ssid": "simulator"},
            "firmware_version": "simulated",
        }
        return telemetry, events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--confirm-synthetic", action="store_true", help="required: acknowledge that this fabricates data")
    parser.add_argument("--allow-remote", action="store_true", help="permit a non-localhost backend (dangerous)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="backend base URL")
    parser.add_argument("--device-id", default="ESP32-SIM", help="simulated device id")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between telemetry posts")
    parser.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run until Ctrl-C)")
    args = parser.parse_args()

    if not args.confirm_synthetic:
        print("refusing to run: this script fabricates telemetry.", file=sys.stderr)
        print("re-run with --confirm-synthetic if that is what you want.", file=sys.stderr)
        return 2

    from urllib.parse import urlparse

    parsed = urlparse(args.base_url)
    if parsed.hostname not in LOCAL_HOSTS and not args.allow_remote:
        print(f"refusing to send synthetic data to {parsed.hostname!r} without --allow-remote", file=sys.stderr)
        return 2

    try:
        health = get(f"{args.base_url}/api/health")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"backend not reachable at {args.base_url}: {error}", file=sys.stderr)
        print("start it with 'make backend' first.", file=sys.stderr)
        return 1

    print(f"connected to {args.base_url} (version {health.get('version')})")
    print(f"posting SYNTHETIC telemetry for {args.device_id}; Ctrl-C to stop")

    scenario = Scenario(args.device_id)
    try:
        while args.ticks == 0 or scenario.tick < args.ticks:
            telemetry, events = scenario.next_payload()
            try:
                post(f"{args.base_url}/api/telemetry", telemetry)
                if events:
                    post(
                        f"{args.base_url}/api/events",
                        {"device_id": args.device_id, "events": events},
                    )
                print(
                    f"[{scenario.tick:>3}] {telemetry['robot']['state']:<19}"
                    f" {telemetry['sensors']['distance_cm']:>6.1f} cm"
                    f" emitter={'ON ' if telemetry['emitter']['active'] else 'off'}"
                )
            except (urllib.error.URLError, TimeoutError) as error:
                print(f"post failed: {error}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
