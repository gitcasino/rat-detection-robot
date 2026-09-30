# Architecture

## Context

```
   ┌────────────────────────┐   HTTP (telemetry + events)   ┌──────────────────────┐
   │  ESP32 firmware        │ ────────────────────────────▶ │  FastAPI backend     │
   │  sensors → state       │                               │  ingest → reconcile  │
   │  machine → outputs     │ ◀─────────────────────────── │  persist → broadcast │
   │  telemetry queue       │        HTTP 200 + ack        │  SQLite + WebSocket  │
   └────────────────────────┘                               └──────────┬───────────┘
                                                                       │ WS
                                                                       ▼
                                                            ┌──────────────────────┐
                                                            │  React console       │
                                                            │  store → panels → log│
                                                            └──────────────────────┘
```

Control flows one way: the firmware decides, the backend records and reconciles,
the console displays. The console never writes to the robot, and the backend
never commands hardware.

## Firmware

`firmware/robot/robot.ino` is a single non-blocking loop:

1. `robot_network::tick` advances the Wi-Fi reconnect state machine and keeps NTP fresh.
2. `sensors::poll` runs the HC-SR04 echo state machine and debounces the digital
   channels. Nothing waits for a measurement.
3. `robotlogic::Controller::update` decides the next `RobotState` and the requested
   outputs. This module is pure C++ with no Arduino dependency, which is why it can
   be unit tested on a host.
4. `motors::apply` and `emitter::set_active` write the pins. `emitter::set_active`
   is the only writer of the emitter pin and reports whether the command changed.
5. Transitions and sensor edges are recorded into a bounded RAM queue; HTTP work
   happens in `telemetry::flush`, at most one request per flush interval.

### State machine

```
                 ┌────────────┐  target confirmed   ┌────────────────┐
                 │    IDLE    │ ──────────────────▶ │ TARGET_DETECTED│
                 └────────────┘                    └───────┬────────┘
                        ▲                                   │ advance
                        │ stop                             ▼
                 ┌────────────┐   emitter burst   ┌──────────────────┐
                 │ MONITORING │ ◀───────────────▶ │  APPROACHING     │
                 └────────────┘                  └────────┬─────────┘
                        ▲                                │ obstacle
                        │                                ▼
                        │                        ┌──────────────────────┐
                        │          cleared       │ OBSTACLE_AVOIDANCE  │
                        └────────────────────────┴──────────────────────┘

Any state ──hardware incomplete or distance lost──▶ ERROR
```

`TARGET_DETECTED` is stationary on purpose: the robot stands still while it
confirms. Only `APPROACHING` and `OBSTACLE_AVOIDANCE` command motion, which is
exactly how the backend decides when to write `ROBOT_MOVING` and `ROBOT_STOPPED`.

### Safety invariants (enforced in `robot_logic.cpp`, covered by tests)

- The emitter is only requested while the drive is stopped.
- A burst is bounded by `CFG_EMITTER_BURST_MS`, followed by
  `CFG_EMITTER_COOLDOWN_MS`, with at most `CFG_EMITTER_MAX_BURSTS_PER_ACTIVITY`
  bursts per activity episode.
- If both the drive and the emitter are unconfigured, or the distance reading is
  stale, the machine faults to `ERROR` and requests neither.
- `setup()` forces emitter off and motors stopped, and `robot.ino` refuses to
  drive for the first 500 ms.
- The control loop never blocks on the network; telemetry failure only fills the
  queue (bounded at `CFG_EVENT_QUEUE_CAPACITY`).

## Backend

FastAPI with a service layer:

- `app/api/telemetry.py` - device ingestion, payload limit, API key / allowlist.
- `app/api/events.py` - event batch ingestion and history queries.
- `app/api/devices.py` - device state, consolidated status, statistics.
- `app/api/health.py` - liveness, readiness, schema version.
- `app/api/stream.py` - `/ws` and `/ws/{device_id}`, per-client queue with
  keepalive.
- `app/services/telemetry.py` - validation, presence, transition reconciliation.
- `app/services/events.py` - persistence, de-duplication, emitter sessions.
- `app/services/realtime.py` - frame serialisation and broadcast.
- `app/services/devices.py` - offline marking and device projections.

### Three kinds of record

| Record | Table | Purpose |
| --- | --- | --- |
| Device state | `devices` | Current, mutated in place; one row per device |
| Telemetry sample | `telemetry_samples` | Rate-limited history (`TELEMETRY_PERSIST_INTERVAL_S`) |
| Event | `events` | Immutable, append-only, queried and exported |

Event rows are never updated. That is what makes the history an audit trail:
emitter durations, for example, are computed from activation and deactivation
events rather than from a mutable counter.

### Reconciliation

The server treats the device as authoritative for the current state, but it
re-derives transitions so that a lost event still yields a coherent history:

- A rise of `emitter_active` writes `EMITTER_ACTIVATED` (`source=SERVER`) and
  opens an emitter session.
- A fall of `emitter_active` writes `EMITTER_DEACTIVATED` and closes the session,
  recording the measured duration.
- Robot state changes write `ROBOT_MOVING` / `ROBOT_STOPPED` around
  `MOVING_STATES` (`APPROACHING`, `OBSTACLE_AVOIDANCE`).
- Presence transitions write `DEVICE_ONLINE` / `DEVICE_OFFLINE`.
- Telemetry with no change in those four facts still updates the device row and
  `last_seen_at`, but writes no event, so the log stays a log.
- Events that arrive from the device are persisted with `source=DEVICE`. Within
  `DEDUPE_WINDOW_S` (2 s) a repeated event of the same type for the same device
  is dropped, which covers the device and the server describing the same change.

### Failure behaviour

- **Backend down**: the firmware keeps sensing, driving and emitting; events queue
  in RAM and are retried with exponential backoff (2 s to 20 s). The console shows
  `Backend offline` and the last known state.
- **WebSocket blocked but backend up**: the console shows
  `Live stream interrupted`, falls back to REST polling every 20 s and keeps
  reconnecting with jittered backoff.
- **Device silent**: the offline monitor marks the device `OFFLINE` after
  `DEVICE_OFFLINE_TIMEOUT_S` and the console renders the emitter as `OFFLINE`
  rather than pretending it is idle.
- **Duplicate or replayed telemetry**: harmless. The device row is idempotent per
  sample and events are de-duplicated.
- **Bad device clock**: the timestamp is replaced with server time and the event
  is flagged `device_timestamp_rejected`.

## Console

State flows one way: WebSocket frames and REST responses are merged by a pure
reducer (`lib/telemetryReducer.ts`), which de-duplicates events by id because the
same event can arrive from both the snapshot frame and the stream.

- `hooks/useWebSocket.ts` owns the socket lifecycle, keepalive and backoff.
- `hooks/TelemetryProvider.tsx` owns REST polling, the merge path and derived state.
- `hooks/telemetryContext.ts` exposes the store contract to components.
- Components read the store and never fetch directly, except the event drawer
  (activation windows) and the statistics panel.

The store keeps at most 500 events in memory. Older events remain queryable
through the REST history endpoints.

## Concurrency notes

- SQLite runs in WAL mode with `busy_timeout`, and every write happens in a short
  transaction, which is sufficient for one to a few robots.
- The offline monitor is a single asyncio task started in the lifespan hook.
- WebSocket clients each own a bounded queue; a slow client drops frames instead
  of blocking the broadcaster, and the console recovers state from the next
  snapshot.

## Scaling path

The seams that matter if this grows beyond one robot: replace the SQLite URL with
a PostgreSQL URL, move the presence sweep into a scheduled job, and shard events by
`device_id`. None of the service signatures need to change for that.
