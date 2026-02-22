#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
  echo "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Start backend in background
bash scripts/start_backend.sh &
BACKEND_PID=$!

echo "Waiting for backend to start..."
sleep 3

# Start frontend in foreground
bash scripts/start_frontend.sh
