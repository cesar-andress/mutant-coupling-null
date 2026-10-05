#!/usr/bin/env bash
# Run Route A + coupling row for every active bug of one Defects4J project.
set -euo pipefail
PID="${1:?project}"
ROOT="${2:-/opt/artifact}"
OUT_BASE="${3:-$ROOT/results/raw/t5}"
D4J_HOME="${D4J_HOME:-/opt/defects4j}"
export PATH="$D4J_HOME/framework/bin:$PATH"
CSV="$D4J_HOME/framework/projects/$PID/active-bugs.csv"
mkdir -p "$OUT_BASE"
"$ROOT/acquire/apply_killmap_patch.sh" "$D4J_HOME"
mapfile -t BUGS < <(awk -F, 'NR>1{print $1}' "$CSV")
echo "n_active=${#BUGS[@]}" | tee "$OUT_BASE/${PID}_progress.txt"
for bid in "${BUGS[@]}"; do
  echo "$(date -u +%FT%TZ) start $PID-$bid" | tee -a "$OUT_BASE/${PID}_progress.txt"
  set +e
  timeout 1800 "$ROOT/scripts/t5_one_bug.sh" "$PID" "$bid" "$ROOT" "$OUT_BASE"
  rc=$?
  set -e
  echo "$(date -u +%FT%TZ) end $PID-$bid rc=$rc" | tee -a "$OUT_BASE/${PID}_progress.txt"
  if [ "$rc" -eq 124 ]; then
    mkdir -p "$OUT_BASE/${PID}-${bid}"
    echo timeout > "$OUT_BASE/${PID}-${bid}/exclusion.txt"
  fi
done
echo DONE | tee -a "$OUT_BASE/${PID}_progress.txt"
