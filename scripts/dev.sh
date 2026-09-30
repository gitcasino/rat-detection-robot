#!/usr/bin/env bash
# Bring up the backend and the frontend together for local development.
#
# The firmware is not started here: it must be flashed to hardware. See
# docs/hardware.md before the first power-on.
#
# Usage: bash scripts/dev.sh [--backend-only | --frontend-only]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
MODE="all"

case "${1:-}" in
  --backend-only) MODE="backend" ;;
  --frontend-only) MODE="frontend" ;;
  "") ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Python environment missing. Run 'make setup' first." >&2
  exit 1
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Frontend dependencies missing. Run 'make setup' first." >&2
  exit 1
fi

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

if [[ "$MODE" != "frontend" ]]; then
  echo "==> backend on http://localhost:8000 (docs at /api/docs)"
  (cd "$ROOT/backend" && "$VENV/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000) &
  pids+=($!)
fi

if [[ "$MODE" != "backend" ]]; then
  echo "==> frontend on http://localhost:5173"
  (cd "$ROOT/frontend" && npm run dev) &
  pids+=($!)
fi

echo "==> press Ctrl-C to stop"
wait -n
