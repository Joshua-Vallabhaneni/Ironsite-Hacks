#!/usr/bin/env bash
# run_pipeline.sh — convenience wrapper for the Ironsite pipeline
set -euo pipefail

# Load .env if present
if [ -f "$(dirname "$0")/../.env" ]; then
    set -a
    source "$(dirname "$0")/../.env"
    set +a
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT_DIR="${1:-${REPO_ROOT}/IronsiteHackathonData}"
OUT_DIR="${2:-${REPO_ROOT}/outputs}"
MODE="${3:-augmented}"

echo "=============================================="
echo "  IRONSITE PIPELINE"
echo "  Mode: ${MODE}"
echo "  Input: ${INPUT_DIR}"
echo "  Output: ${OUT_DIR}"
echo "=============================================="

cd "${REPO_ROOT}"

python -m src.pipeline \
    --input_dir "${INPUT_DIR}" \
    --out_dir "${OUT_DIR}" \
    --mode "${MODE}" \
    "${@:4}"

echo "=============================================="
echo "  DONE — check ${OUT_DIR} for results"
echo "=============================================="
