#!/usr/bin/env bash
# Full ModelProof run: live (records the LLM cache), then replay in a scratch dir, compare, keep both runs.
# Needs: data fetched (scripts/fetch_data.py), an LLM key in .env. Usage: scripts/run_pipeline.sh
set -euo pipefail
cd "$(dirname "$0")/.."
STAMP=$(date -u +%Y%m%dT%H%M%S)
REPLAY_DIR=$(mktemp -d)

echo "== 1/4 live run (LLM_MODE=record) =="
MODELPROOF_RUN_ID="live-$STAMP" LLM_MODE=record uv run modelproof run --model all --auto-approve

echo "== 2/4 replay run into $REPLAY_DIR (LLM_MODE=replay) =="
MODELPROOF_ARTIFACTS="$REPLAY_DIR" MODELPROOF_RUN_ID="replay-$STAMP" LLM_MODE=replay \
  uv run modelproof run --model all --auto-approve

echo "== 3/4 compare live and replay artifacts =="
uv run python scripts/replay_check.py artifacts "$REPLAY_DIR"

echo "== 4/4 keep the replay run log, write metrics.json and the README table =="
cp -R "$REPLAY_DIR/runs/replay-$STAMP" "artifacts/runs/replay-$STAMP"
uv run modelproof benchmark
uv run modelproof verify-audit
