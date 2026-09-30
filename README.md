# Smart Rat Detection and Repellent Robot

A three-part telemetry system for a rodent-detection robot:

| Layer | Stack | Responsibility |
| --- | --- | --- |
| Firmware | ESP32 (Arduino framework, C++17) | Sense, decide, drive, repel, report |
| Backend | Python 3.12, FastAPI, SQLAlchemy, SQLite | Ingest, reconcile, persist, stream |
| Console | React 18, TypeScript, Vite, Framer Motion | Live telemetry and event history |

The ESP32 is the only source of physical truth. The backend never invents data and
the console never fabricates it: an empty database renders an honest empty state.

---

## What the system does

1. An ultrasonic rangefinder reports distance; contact/vibration and infrared
   channels report presence. Distance alone never identifies a rat, so the
   firmware requires sensor fusion before it treats something as a target.
2. The robot state machine decides between idle, confirming, approaching,
   avoiding an obstacle, emitting and monitoring.
3. The emitter is driven only while the chassis is stationary, in bounded bursts
   with a cooldown and a per-activity burst cap.
4. The robot posts telemetry and queued events to the backend. If the network
   fails, the control loop keeps running and events queue in RAM.
5. The backend validates, de-duplicates, reconciles transitions and broadcasts
   state over WebSocket while a React console renders it.

## Repository layout

```
rat-detection-robot/
├── backend/            FastAPI service and pytest suite
│   ├── app/            config, db, models, schemas, services, api, websocket
│   ├── tests/          65 tests covering ingest, events, WS, offline, stats
│   └── requirements.txt
├── firmware/robot/     ESP32 sources (config.h, sensors, motors, emitter, ...)
│   └── config.example.h
├── frontend/           React + TypeScript console
│   └── src/{components,hooks,lib,pages,test,types,styles}
├── tools/              native firmware tests, Arduino API stubs, check script
├── docs/               architecture, hardware, telemetry contracts
└── Makefile            setup / dev / test / build targets
```

## Quick start

Requirements: Python 3.11+, Node 18+, a C++17 compiler, and the Arduino IDE or
`arduino-cli` for firmware.

```bash
make setup            # Python venv + npm install
make backend          # http://localhost:8000 (docs at /api/docs)
make frontend         # http://localhost:5173
```

Firmware: open `firmware/robot/robot.ino` in the Arduino IDE, pick an ESP32
board, copy `firmware/robot/config.example.h` to `config.local.h`, fill in the
Wi-Fi credentials and the pins you have actually verified, then upload.
`make firmware-check` type-checks the sources on a host machine without the
Arduino toolchain (see [Limitations](#limitations)).

## Configuration

| Where | File | Notes |
| --- | --- | --- |
| Backend | `backend/.env` (copy from `backend/.env.example`) | Ports, database, CORS, timeouts, optional API keys |
| Frontend | `frontend/.env.local` (copy from `frontend/.env.example`) | API base URL, WebSocket URL, dev port |
| Firmware | `firmware/robot/config.local.h` (copy from `config.example.h`) | Wi-Fi, backend host, pins, thresholds, timings |

Secrets never live in tracked files: `.env`, `.env.local`, `config.local.h` and
`*.db` are all git-ignored.

### Firmware knobs that matter most

| Macro | Default | Meaning |
| --- | --- | --- |
| `DEVICE_ID` | `ESP32-01` | Must match what the backend expects |
| `BACKEND_HOST` / `BACKEND_PORT` | `192.168.1.10` / `8000` | Where telemetry is posted |
| `API_KEY` | empty | Sent as `X-API-Key`; must match backend `API_KEYS` |
| `CFG_TARGET_CONFIRMATION` | `TARGET_CONFIRM_FUSION` | `..._DISTANCE_ONLY` or `..._DISABLED` |
| `CFG_DETECT_DISTANCE_CM` | `20.0f` | Distance treated as close (prototype value) |
| `CFG_EMITTER_BURST_MS` | `3000UL` | Maximum continuous emitter command |
| `CFG_EMITTER_COOLDOWN_MS` | `8000UL` | Minimum gap between bursts |
| `CFG_EMITTER_MAX_BURSTS_PER_ACTIVITY` | `3UL` | Burst cap per activity episode |

`TARGET_CONFIRM_DISTANCE_ONLY` is provided for bench testing. The console labels
that mode as proximity, never as a rat detection.

## Hardware status

Only two GPIO assignments are known, and they come from the prototype rather than
from a verified schematic: ultrasonic `TRIG = GPIO5`, `ECHO = GPIO18`. Every other
pin is `PIN_UNCONFIGURED` (`-1`), which disables that subsystem and raises an
`ERROR` event instead of guessing. See [docs/hardware.md](docs/hardware.md) for
wiring, power, level shifting and the verification checklist.

The emitter panel reports the **command state**, not measured acoustic output:
there is no feedback circuit, so the firmware cannot confirm that sound was
produced.

## Development commands

```bash
make setup           # install backend requirements and frontend dependencies
make backend         # uvicorn with reload
make frontend        # vite dev server
make test            # backend pytest + frontend vitest
make firmware-check  # native logic tests + Arduino-facing syntax check
make lint            # frontend eslint
make typecheck       # frontend tsc
make build           # frontend production build
make check           # everything above, in order
make simulator       # opt-in synthetic telemetry against a local backend
```

## Testing

```bash
cd backend && ../.venv/bin/python -m pytest -q     # 65 passed
cd frontend && npm test                            # 58 passed
bash tools/check_firmware.sh                       # 58 logic + 12 JSON checks, syntax check
```

The backend suite covers payload validation, size limits, timestamp rejection,
telemetry persistence and rate limiting, event ingestion and history queries,
emitter activation and deactivation with measured durations, de-duplication,
device offline/reconnect transitions, WebSocket delivery, statistics, settings and
the guarantee that a fresh database stays empty. The frontend suite covers the
API client, formatters, reducer merge rules and the rendered console, including
stream-driven updates and the three link states (live, degraded, offline).

## Documentation

- [docs/architecture.md](docs/architecture.md) - components, data flow, state
  machine, reconciliation and failure behaviour
- [docs/hardware.md](docs/hardware.md) - wiring, power budget, safety checklist
- [docs/telemetry.md](docs/telemetry.md) - payloads, event vocabulary, clock
  model, WebSocket frames, REST reference

## Limitations

- No Arduino toolchain was available in the development environment, so the
  firmware is verified by native unit tests and a stub-based syntax check, not by
  a board compile or a hardware run.
- Physical wiring is unverified. Unknown pins stay disabled rather than assumed.
- The backend has no authentication beyond optional shared API keys; it is meant
  for a trusted LAN. Do not expose it to the public internet as-is.
- Emitter activation is open-loop. Adding an amplifier or piezo feedback input
  would let the system report verified output instead of a commanded state.
- A single SQLite file is used for persistence, which is ample for one robot but
  not for a fleet.

## License

MIT. See [LICENSE](LICENSE).
