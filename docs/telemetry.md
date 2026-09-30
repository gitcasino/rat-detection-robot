# Telemetry contract

Version: `schema_version = 1`. Every request model allows unknown fields, so a
newer firmware can add sections without breaking the server; the fields the server
relies on are validated strictly.

Unknown fields are stored per event in `metadata`, which is how extra firmware
detail reaches the console without a schema change.

## Vocabulary

| Group | Values |
| --- | --- |
| Device state | `ONLINE`, `OFFLINE` (server-observed presence) |
| Emitter view state | `ACTIVE`, `INACTIVE`, `OFFLINE` (derived in the console) |
| Robot state | `IDLE`, `TARGET_DETECTED`, `APPROACHING`, `OBSTACLE_AVOIDANCE`, `EMITTER_ACTIVE`, `MONITORING`, `ERROR` |
| Event source | `DEVICE` (reported by the robot), `SERVER` (reconciled by the backend) |
| Event category | `EMITTER`, `SENSORS`, `ROBOT`, `SYSTEM`, `ERROR` |

### Event types

| Type | Category | Typical origin |
| --- | --- | --- |
| `DEVICE_ONLINE` / `DEVICE_OFFLINE` | `SYSTEM` | Server, presence transition |
| `VIBRATION_DETECTED` / `VIBRATION_CLEARED` | `SENSORS` | Device, debounced edge |
| `IR_DETECTED` / `IR_CLEARED` | `SENSORS` | Device, debounced edge |
| `DISTANCE_UPDATED` | `SENSORS` | Device, optional (default off) |
| `TARGET_ACTIVITY_DETECTED` / `TARGET_ACTIVITY_CLEARED` | `SENSORS` | Device, sensor fusion |
| `OBSTACLE_DETECTED` / `OBSTACLE_CLEARED` | `ROBOT` | Device, clearance threshold |
| `ROBOT_MOVING` / `ROBOT_STOPPED` | `ROBOT` | Server, state transition |
| `EMITTER_ACTIVATED` / `EMITTER_DEACTIVATED` | `EMITTER` | Server (device also reports) |
| `HEARTBEAT` | `SYSTEM` | Device, disabled by default |
| `ERROR` | `ERROR` | Device or server, with a message |

## Device to backend

### `POST /api/telemetry`

```json
{
  "schema_version": 1,
  "device_id": "ESP32-01",
  "timestamp": "2026-03-01T10:00:00Z",
  "uptime_ms": 3600000,
  "emitter": { "active": false, "mode": "BURST", "commanded_by": "firmware" },
  "sensors": { "vibration": false, "ir_detected": false, "distance_cm": 42.5, "distance_valid": true },
  "robot": { "state": "IDLE", "left_motor": 0, "right_motor": 0, "obstacle_distance_cm": 120.0 },
  "network": { "rssi": -58, "ip": "192.168.1.42", "ssid": "lab-net", "channel": 6 },
  "firmware_version": "1.0.0"
}
```

Accepted with `200 OK`:

```json
{
  "accepted": true,
  "device_id": "ESP32-01",
  "received_at": "2026-03-01T10:00:00.512000Z",
  "server_time_ms": 1772364000512,
  "events": [],
  "device_state": "ONLINE"
}
```

`events` contains any transitions the server reconciled from this payload, which
lets the firmware log a single server response instead of guessing.

Validation and limits:

- `device_id` must match `^[A-Za-z0-9._:-]+$` (1 to 64 characters).
- `distance_cm` must be 0 to 1000 and a real number (`NaN` is rejected).
- `distance_valid: false` means "no reading"; the last distance is not invented.
- Bodies larger than `MAX_PAYLOAD_BYTES` (64 KiB) get `413`.
- `ALLOWED_DEVICE_IDS` and `API_KEYS` add an optional device allowlist and the
  `X-API-Key` header requirement.

### `POST /api/events`

```json
{
  "schema_version": 1,
  "device_id": "ESP32-01",
  "uptime_ms": 3600000,
  "events": [
    {
      "type": "VIBRATION_DETECTED",
      "timestamp": "2026-03-01T10:00:00Z",
      "distance_cm": 18.2,
      "vibration": true,
      "ir_detected": false,
      "emitter_active": false,
      "robot_state": "TARGET_DETECTED",
      "message": "Vibration sensor triggered",
      "metadata": { "sensor": "piezo", "threshold_ms": 120 }
    }
  ]
}
```

Up to 64 events per request. The response reports `accepted_count`, the list of
`duplicates`, and the stored `events`. A repeated event of the same type for the
same device inside the 2-second de-duplication window is dropped rather than
stored twice.

Timestamps may be ISO-8601, epoch seconds, or epoch milliseconds. Values more
than `DEVICE_CLOCK_SKEW_TOLERANCE_S` (900 s) from server time are replaced with
the server clock and the stored event carries `device_timestamp_rejected: true`.

## Backend to console

### `GET /api/status`

Everything the console needs for a first paint, in one call: `server_time`,
`backend` link status, device counts, `primary_device_id` and the full `devices`
array with `emitter_active`, `emitter_activated_at`, `emitter_active_seconds`,
`emitter_activations`, `open_session`, robot state, distance, radio and uptime.

### Other read endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/devices` | All device states |
| `GET /api/devices/{device_id}` | One device state |
| `GET /api/devices/{device_id}/emitter-sessions?limit=25` | Activation windows with measured durations |
| `GET /api/events?device_id=&type=&category=&search=&since=&until=&order=&limit=&offset=` | Paginated history (`type` and `category` repeat) |
| `GET /api/events/{id}` | One event |
| `GET /api/stats?window_hours=24` | Counts by type and category, emitter totals, hourly buckets |
| `GET /api/health` | Liveness, database check, version, schema version |
| `GET /api/docs`, `GET /api/openapi.json` | Interactive API reference |

### WebSocket `/ws` and `/ws/{device_id}`

```json
{ "type": "snapshot", "server_time": "...", "backend": { "websocket": "connected", "websocket_clients": 1, "backend": "online" },
  "devices": [ ... ], "events": [ ... ], "device_filter": null }
```

| Frame | When |
| --- | --- |
| `snapshot` | On connect, and after a server restart: full device state plus recent events |
| `telemetry` | Every accepted telemetry payload, with the resulting device state |
| `events` | New events for a device, newest first |
| `device` | A device presence or state change |
| `pong` | Answer to a client `{"type":"ping"}`; the server also pings on its own |
| `error` | A recoverable stream problem, with `detail` |

The console sends `{"type": "ping"}` every 20 s. A dropped socket is retried with
jittered exponential backoff up to 15 s, and the console falls back to REST
polling so it keeps showing the last known state.

## Semantics worth remembering

- **Distance is not identity.** `TARGET_ACTIVITY_*` means sensor fusion fired.
- **Emitter state is a command.** `EMITTER_ACTIVATED` means the driver pin was
  asserted, not that sound was measured.
- **Transitions, not samples.** The emitter produces one event on change, never
  one per loop. `ROBOT_MOVING` appears when the state enters a moving state, and
  `ROBOT_STOPPED` when it leaves one. `TARGET_DETECTED` is stationary and produces
  neither.
- **The server is the clock authority**; the device clock is accepted only when it
  is plausible.

## Trying it by hand

With the backend running:

```bash
curl -s localhost:8000/api/telemetry -H 'Content-Type: application/json' -d '{
  "device_id": "ESP32-01",
  "sensors": {"distance_cm": 18.0, "vibration": true, "distance_valid": true},
  "robot": {"state": "TARGET_DETECTED"},
  "network": {"rssi": -55}
}'

curl -s 'localhost:8000/api/events?limit=5&category=EMITTER'
curl -s localhost:8000/api/status
```

For a scripted walk-through of the full lifecycle, `scripts/simulate_telemetry.py`
posts synthetic events. It is a development tool, it is opt-in, and it must never
point at a database you care about.
