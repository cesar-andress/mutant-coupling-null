#!/usr/bin/env bash
# Route A kill map + coupling row for one bug. Timeout-bounded.
set -euo pipefail
PID="$1"
BID="$2"
ROOT="${3:-/opt/artifact}"
OUT_BASE="${4:-$ROOT/results/raw/t5}"
OUT="$OUT_BASE/${PID}-${BID}"
mkdir -p "$OUT"
D4J_HOME="${D4J_HOME:-/opt/defects4j}"
export PATH="$D4J_HOME/framework/bin:$PATH" PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [ ! -f "$OUT/killMap.csv" ]; then
  "$ROOT/scripts/route_a_killmap.sh" "$PID" "$BID" "$OUT"
fi
TRIG="$D4J_HOME/framework/projects/$PID/trigger_tests/$BID"
if [ ! -f "$TRIG" ]; then
  echo "missing trigger file" > "$OUT/exclusion.txt"
  exit 2
fi
cp "$TRIG" "$OUT/trigger_tests.txt"
/usr/bin/python3 "$ROOT/scripts/compute_anchor_row.py" "$PID" "$BID" "$OUT" "$TRIG" "$OUT/anchor.json"
