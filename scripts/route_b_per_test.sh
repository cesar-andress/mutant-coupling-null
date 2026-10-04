#!/usr/bin/env bash
# Route B: stock per-test-method defects4j mutation (no exportKillMap patch).
set -euo pipefail
PID="${1:?project}"
BID="${2:?bug id}"
OUT="${3:?output directory}"
D4J_HOME="${D4J_HOME:-/opt/defects4j}"
export PATH="$D4J_HOME/framework/bin:$PATH" PYTHONPATH="${PYTHONPATH:-}:/opt/artifact/src"
export TZ="${TZ:-America/Los_Angeles}"
VID="${BID}f"
WORKDIR="${WORKDIR:-/work/checkout/${PID}-${VID}-b}"
mkdir -p "$OUT/per_test" "$WORKDIR"
if grep -q 'exportKillMap="true"' "$D4J_HOME/framework/projects/defects4j.build.xml"; then
  echo "error: Route B requires stock (unpatched) defects4j.build.xml" >&2
  exit 1
fi
defects4j checkout -p "$PID" -v "$VID" -w "$WORKDIR"
defects4j compile -w "$WORKDIR"
SRC_TESTS="$(defects4j export -p dir.src.tests -w "$WORKDIR" | tail -n1)"
mapfile -t CLASSES < <(defects4j export -p tests.relevant -w "$WORKDIR" | awk 'NF && $0 !~ /^Running /')
python3 - "$WORKDIR" "$SRC_TESTS" "$OUT/tests.txt" "${CLASSES[@]}" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "/opt/artifact/src")
from killmap.junit_methods import methods_from_file
work, src_rel, out = sys.argv[1], sys.argv[2], sys.argv[3]
classes = sys.argv[4:]
root = Path(work) / src_rel
rows = []
for cls in classes:
    path = root.joinpath(*cls.split(".")).with_suffix(".java")
    if not path.is_file():
        raise SystemExit(f"missing test source {path}")
    for meth in methods_from_file(path):
        rows.append(f"{cls}::{meth}")
Path(out).write_text("\n".join(rows) + ("\n" if rows else ""))
print(f"n_methods={len(rows)}")
PY
n=0
ok=0
fail=0
start=$(date +%s)
while IFS= read -r t; do
  [ -z "$t" ] && continue
  n=$((n+1))
  safe="${t//::/__}"
  dest="$OUT/per_test/$safe"
  mkdir -p "$dest"
  set +e
  /usr/bin/time -f $'wall_sec=%e\nuser_sec=%U\nsys_sec=%S\nmax_rss_kb=%M' -o "$dest/mutation.time" \
    defects4j mutation -w "$WORKDIR" -t "$t" >"$dest/mutation.stdout" 2>"$dest/mutation.stderr"
  rc=$?
  set -e
  echo "$rc" >"$dest/mutation.exit"
  if [ -f "$WORKDIR/kill.csv" ]; then
    cp "$WORKDIR/kill.csv" "$dest/kill.csv"
  fi
  if [ "$rc" -eq 0 ]; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
    echo "FAIL $t rc=$rc" | tee -a "$OUT/failures.txt"
  fi
done < "$OUT/tests.txt"
end=$(date +%s)
{
  echo "n_tests=$n"
  echo "ok=$ok"
  echo "fail=$fail"
  echo "elapsed_epoch_sec=$((end-start))"
} | tee "$OUT/DONE"
