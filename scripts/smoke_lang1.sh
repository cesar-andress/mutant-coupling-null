#!/usr/bin/env bash
# T3 smoke: Lang-1 FIXED, stock defects4j mutation. No exportKillMap. No coupling stats.
set -euo pipefail

# shellcheck source=/dev/null
source "${PIN_ENV:-/opt/artifact/env/pin.env}"

TASK_ID="T3"
PID="Lang"
BID="1"
VID="1f"
D4J_HOME="${D4J_HOME:-/opt/defects4j}"
export PATH="$D4J_HOME/framework/bin:$PATH"
export TZ="${TZ:-America/Los_Angeles}"

RESULTS_DIR="${RESULTS_DIR:-/work/results}"
WORK_DIR="${WORK_DIR:-/work/checkout/Lang-1f}"
mkdir -p "$RESULTS_DIR" "$WORK_DIR"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

TIME_BIN=""
if command -v /usr/bin/time >/dev/null 2>&1; then
  TIME_BIN=/usr/bin/time
fi

run_timed() {
  local name="$1"
  shift
  local start end
  start="$(date +%s)"
  set +e
  if [ -n "$TIME_BIN" ]; then
    "$TIME_BIN" -f $'wall_sec=%e\nuser_sec=%U\nsys_sec=%S\nmax_rss_kb=%M' \
      -o "$RESULTS_DIR/${name}.time" \
      "$@" >"$RESULTS_DIR/${name}.stdout" 2>"$RESULTS_DIR/${name}.stderr"
  else
    "$@" >"$RESULTS_DIR/${name}.stdout" 2>"$RESULTS_DIR/${name}.stderr"
    echo "wall_sec=NOT_MEASURED max_rss_kb=NOT_MEASURED" >"$RESULTS_DIR/${name}.time"
  fi
  local rc=$?
  set -e
  end="$(date +%s)"
  echo "$rc" >"$RESULTS_DIR/${name}.exit"
  echo "elapsed_epoch_sec=$((end - start))" >>"$RESULTS_DIR/${name}.time"
  return "$rc"
}

log "environment checks"
/opt/artifact/tests/test_environment.sh | tee "$RESULTS_DIR/environment_checks.txt"

log "record versions"
{
  echo "=== java -version ==="
  java -version 2>&1
  echo "=== java vendor ==="
  java -XshowSettings:properties -version 2>&1 | grep -E 'java\.(vendor|vm.vendor|runtime.version|vm.version)' || true
  echo "=== perl ==="
  perl -v | head -n 3
  echo "=== ant (Major wrapper) ==="
  "$D4J_HOME/major/bin/ant" -version || true
  echo "=== maven ==="
  (command -v mvn >/dev/null && mvn -version) || echo "mvn not on PATH (expected unless a project invokes it)"
  echo "=== defects4j ==="
  defects4j 2>&1 | head -n 5 || true
  echo "=== git sha ==="
  git -C "$D4J_HOME" rev-parse HEAD
  echo "=== major tree ==="
  ls -1 "$D4J_HOME/major" | head
  echo "=== uname ==="
  uname -s -m
  echo "=== os-release ==="
  cat /etc/os-release
} >"$RESULTS_DIR/versions.txt"

# Confirm Lang-1 is active; if not, first active Lang bug only (deterministic, no cherry-pick).
if ! grep -q "^${BID}," "$D4J_HOME/framework/projects/Lang/active-bugs.csv"; then
  BID="$(cut -d, -f1 "$D4J_HOME/framework/projects/Lang/active-bugs.csv" | awk 'NR==2 {print; exit}')"
  VID="${BID}f"
  echo "Lang-1 not active; substituted first active Lang bug ${BID}" | tee "$RESULTS_DIR/bug_substitution.txt"
fi

cp "$D4J_HOME/framework/projects/Lang/trigger_tests/${BID}" "$RESULTS_DIR/trigger_tests.txt"
cp "$D4J_HOME/framework/projects/Lang/modified_classes/${BID}.src" "$RESULTS_DIR/modified_classes.txt"
grep "^${BID}," "$D4J_HOME/framework/projects/Lang/commit-db" >"$RESULTS_DIR/commit-db-row.txt" || true

log "checkout ${PID}-${VID}"
run_timed checkout defects4j checkout -p "$PID" -v "$VID" -w "$WORK_DIR" || true

log "compile"
run_timed compile defects4j compile -w "$WORK_DIR" || true

log "relevant tests"
run_timed tests defects4j test -r -w "$WORK_DIR" || true

log "stock mutation (relevant tests, no exportKillMap)"
if grep -q exportKillMap "$D4J_HOME/framework/projects/defects4j.build.xml"; then
  echo "error: exportKillMap present; T3 forbids that patch" >&2
  exit 1
fi
run_timed mutation defects4j mutation -r -w "$WORK_DIR" || true

python3 - "$WORK_DIR" "$RESULTS_DIR" <<'PY'
import json, os, sys, glob
work, out = sys.argv[1], sys.argv[2]
patterns = [
    "summary.csv", "kill.csv", "mutants.log", "testMap.csv",
    "covMap.csv", "killMap.csv", ".mutation.log",
]
found = []
for name in patterns:
    path = os.path.join(work, name)
    if os.path.isfile(path):
        found.append({
            "filename": name,
            "bytes": os.path.getsize(path),
        })
# also list *.csv at work root
root_csv = sorted(os.path.basename(p) for p in glob.glob(os.path.join(work, "*.csv")))
with open(os.path.join(out, "output_inventory.json"), "w", encoding="utf-8") as fh:
    json.dump({"work_root_csv": root_csv, "known_files": found}, fh, indent=2)
    fh.write("\n")
# copy small summaries
for name in ("summary.csv", "kill.csv", "mutants.log", "testMap.csv", "covMap.csv"):
    src = os.path.join(work, name)
    if os.path.isfile(src) and os.path.getsize(src) <= 2_000_000:
        with open(src, "rb") as inf, open(os.path.join(out, name), "wb") as outf:
            outf.write(inf.read())
PY

log "write manifest"
python3 - "$RESULTS_DIR" "$PID" "$BID" "$VID" "$DEFECTS4J_SHA" "$DEFECTS4J_TAG" "$MAJOR_VERSION" <<'PY'
import json, os, sys, glob, re
out, pid, bid, vid, sha, tag, major = sys.argv[1:8]

def read(p):
    fp = os.path.join(out, p)
    if not os.path.isfile(fp):
        return None
    with open(fp, encoding="utf-8", errors="replace") as fh:
        return fh.read().strip()

def parse_time(name):
    text = read(name) or ""
    d = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v
    return d

mutants = None
summary = read("summary.csv")
if summary:
    lines = [ln for ln in summary.splitlines() if ln.strip()]
    if len(lines) >= 2:
        parts = lines[1].split(",")
        try:
            mutants = int(parts[0])
        except (ValueError, IndexError):
            mutants = None

tests_stdout = read("tests.stdout") or ""
failing = None
m = re.search(r"Failing tests:\s*(\d+)", tests_stdout)
if m:
    failing = int(m.group(1))

inventory = json.loads(read("output_inventory.json") or "{}")
image_id = os.environ.get("IMAGE_ID", "")

manifest = {
    "task_id": "T3",
    "project": pid,
    "bug_id": bid,
    "revision": "FIXED",
    "version_id": vid,
    "defects4j_requested_version": "3.0.1",
    "defects4j_tag": tag,
    "defects4j_sha": sha,
    "defects4j_upstream": "https://github.com/rjust/defects4j.git",
    "major_version": major,
    "java_major": "11",
    "container_base": "ubuntu:22.04",
    "image_id": image_id or None,
    "commands": [
        "defects4j checkout -p Lang -v 1f",
        "defects4j compile",
        "defects4j test -r",
        "defects4j mutation -r",
    ],
    "exit_statuses": {
        "checkout": int(read("checkout.exit") or -1),
        "compile": int(read("compile.exit") or -1),
        "tests": int(read("tests.exit") or -1),
        "mutation": int(read("mutation.exit") or -1),
    },
    "runtime": {
        "checkout": parse_time("checkout.time"),
        "compile": parse_time("compile.time"),
        "tests": parse_time("tests.time"),
        "mutation": parse_time("mutation.time"),
    },
    "failing_tests_reported": failing,
    "mutants_generated": mutants,
    "output_files": inventory,
    "exportKillMap": False,
    "per_test_kill_matrix": False,
    "coupling_calculated": False,
    "paid_external_apis": 0,
    "gpu": False,
    "uname": os.uname().sysname + " " + os.uname().machine,
}
with open(os.path.join(out, "T3_SMOKE_MANIFEST.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2)
    fh.write("\n")
print(json.dumps({"mutants_generated": mutants, "mutation_exit": manifest["exit_statuses"]["mutation"]}))
PY

mutation_rc="$(cat "$RESULTS_DIR/mutation.exit")"
if [ "$mutation_rc" != "0" ]; then
  log "mutation failed; see mutation.stderr"
  exit "$mutation_rc"
fi
log "smoke complete"
