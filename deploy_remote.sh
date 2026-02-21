#!/usr/bin/env bash
# deploy_remote.sh — Run this LOCALLY. It will SSH into the remote,
# transfer code, install deps, and run the pipeline.
# Usage: bash deploy_remote.sh
set -euo pipefail

REMOTE="root@142.117.93.98"
PORT=36339
REPO_ROOT="/Users/joshuavallabhaneni/Ironsite-Hacks"

echo "=== Packing code ==="
cd "${REPO_ROOT}"
tar czf /tmp/ironsite_code.tar.gz \
  --exclude='.git' \
  --exclude='IronsiteHackathonData' \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  --exclude='outputs' .

echo "=== Transferring to remote ==="
scp -P ${PORT} /tmp/ironsite_code.tar.gz ${REMOTE}:/tmp/ironsite_code.tar.gz

echo "=== Deploying on remote ==="
ssh -p ${PORT} ${REMOTE} << 'REMOTE_SCRIPT'
set -euo pipefail

echo "=== Extracting code ==="
cd /workspace/Ironsite-Hacks
tar xzf /tmp/ironsite_code.tar.gz

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Setting API key ==="
export GEMINI_API_KEY=""

echo "=== Running pipeline (rules_only, 1 video test) ==="
python -m src.pipeline \
  --input_dir /workspace/Ironsite-Hacks/IronsiteHackathonData \
  --out_dir /workspace/Ironsite-Hacks/outputs \
  --mode rules_only \
  --max_videos 1

echo "=== DONE ==="
ls -la /workspace/Ironsite-Hacks/outputs/*/
REMOTE_SCRIPT
