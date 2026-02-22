#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Source .env if present
if [ -f .env ]; then
  set -a; source .env; set +a
fi

exec uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
