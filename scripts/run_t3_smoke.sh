#!/usr/bin/env bash
# Build the pinned image and run the Lang-1 smoke test.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-mutant-coupling-null:t3-env}"
RESULTS_HOST="${RESULTS_HOST:-$ROOT/results/raw/smoke}"
mkdir -p "$RESULTS_HOST"

docker build -f "$ROOT/env/Dockerfile" -t "$IMAGE_NAME" "$ROOT"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_NAME")"
echo "$IMAGE_ID" >"$RESULTS_HOST/image_id.txt"

docker run --rm \
  --network none \
  -e IMAGE_ID="$IMAGE_ID" \
  -e RESULTS_DIR=/work/results \
  -v "$RESULTS_HOST:/work/results" \
  "$IMAGE_NAME" \
  /opt/artifact/scripts/smoke_lang1.sh
