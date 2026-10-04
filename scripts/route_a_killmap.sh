#!/usr/bin/env bash
# Route A: patched defects4j mutation -r with exportKillMap (method-level).
set -euo pipefail
PID="${1:?project}"
BID="${2:?bug id}"
OUT="${3:?output directory}"
D4J_HOME="${D4J_HOME:-/opt/defects4j}"
export PATH="$D4J_HOME/framework/bin:$PATH"
export TZ="${TZ:-America/Los_Angeles}"
VID="${BID}f"
WORKDIR="${WORKDIR:-/work/checkout/${PID}-${VID}}"
mkdir -p "$OUT" "$WORKDIR"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$SCRIPT_ROOT/acquire/apply_killmap_patch.sh" ]; then
  "$SCRIPT_ROOT/acquire/apply_killmap_patch.sh" "$D4J_HOME"
elif [ -x /opt/artifact/acquire/apply_killmap_patch.sh ]; then
  /opt/artifact/acquire/apply_killmap_patch.sh "$D4J_HOME"
fi
if ! grep -q 'exportKillMap="true"' "$D4J_HOME/framework/projects/defects4j.build.xml"; then
  echo "error: kill-map patch missing" >&2
  exit 1
fi
TIME_BIN=""
command -v /usr/bin/time >/dev/null && TIME_BIN=/usr/bin/time
run() {
  local name="$1"; shift
  local start end rc
  start="$(date +%s)"
  set +e
  if [ -n "$TIME_BIN" ]; then
    "$TIME_BIN" -f $'wall_sec=%e\nuser_sec=%U\nsys_sec=%S\nmax_rss_kb=%M' -o "$OUT/${name}.time" \
      "$@" >"$OUT/${name}.stdout" 2>"$OUT/${name}.stderr"
  else
    "$@" >"$OUT/${name}.stdout" 2>"$OUT/${name}.stderr"
  fi
  rc=$?
  set -e
  end="$(date +%s)"
  echo "$rc" >"$OUT/${name}.exit"
  echo "elapsed_epoch_sec=$((end-start))" >>"$OUT/${name}.time"
  return "$rc"
}
run checkout defects4j checkout -p "$PID" -v "$VID" -w "$WORKDIR"
run compile defects4j compile -w "$WORKDIR"
run tests defects4j test -r -w "$WORKDIR"
run mutation defects4j mutation -r -w "$WORKDIR"
for f in summary.csv kill.csv mutants.log testMap.csv covMap.csv killMap.csv .mutation.log; do
  if [ -f "$WORKDIR/$f" ]; then
    cp -a "$WORKDIR/$f" "$OUT/$f"
  fi
done
echo "route_a_done pid=$PID bid=$BID" | tee "$OUT/DONE"
