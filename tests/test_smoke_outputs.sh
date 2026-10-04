#!/usr/bin/env bash
# Checks that a T3 smoke run left the expected small tracked outputs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE="$ROOT/results/raw/smoke"
fail=0
for f in T3_SMOKE_MANIFEST.json summary.csv versions.txt output_inventory.json; do
  if [ -f "$SMOKE/$f" ]; then
    echo "OK  $f"
  else
    echo "FAIL missing $f" >&2
    fail=1
  fi
done
python3 - "$SMOKE/T3_SMOKE_MANIFEST.json" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    m = json.load(fh)
assert m.get("exportKillMap") is False
assert m.get("per_test_kill_matrix") is False
assert m.get("coupling_calculated") is False
assert m.get("paid_external_apis") == 0
assert m.get("mutants_generated", 0) > 0
assert m.get("exit_statuses", {}).get("mutation") == 0
print("OK  manifest invariants")
PY
exit "$fail"
