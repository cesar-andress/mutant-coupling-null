#!/usr/bin/env python3
"""Resumable full-study acquisition. Outcome-independent. No aggregate effect."""

from __future__ import annotations

import csv
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

STATE_LOCK = threading.Lock()

MAX_PARALLEL = 3
TIMEOUT_SEC = 1800
IMAGE = "mutant-coupling-null:t3-env"
MAPS = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_dir(d: Path) -> str:
    if not d.is_dir():
        return "PENDING"
    maps_ok = all((d / n).is_file() for n in MAPS)
    trig_ok = (d / "trigger_tests.txt").is_file()
    if maps_ok and trig_ok:
        return "COMPLETE_VALID"
    excl = d / "exclusion.txt"
    if excl.is_file() and "timeout" in excl.read_text(errors="replace").lower():
        return "TIMEOUT"
    mut_exit = d / "mutation.exit"
    if mut_exit.is_file():
        try:
            rc = int(mut_exit.read_text().strip() or "1")
        except ValueError:
            rc = 1
        if rc != 0:
            return "MUTATION_FAILURE"
    if (d / "mutation.time").is_file() or (d / "mutation.stderr").is_file():
        if not maps_ok:
            return "TIMEOUT"
    for name in ("compile.exit", "checkout.exit"):
        p = d / name
        if p.is_file():
            try:
                rc = int(p.read_text().strip() or "0")
            except ValueError:
                rc = 1
            if rc != 0:
                return "BUILD_FAILURE"
    if any(d.iterdir()):
        return "OTHER_FAILURE"
    return "PENDING"


def count_lines(path: Path) -> int | None:
    if not path.is_file():
        return None
    n = 0
    with path.open("rb") as fh:
        for _ in fh:
            n += 1
    return max(0, n - 1)


def load_state(path: Path) -> dict[tuple[str, str], dict]:
    if not path.is_file():
        return {}
    out = {}
    with path.open() as fh:
        for rec in csv.DictReader(fh):
            out[(rec["project"], rec["bug_id"])] = rec
    return out


def write_state(path: Path, state: dict[tuple[str, str], dict]) -> None:
    fields = [
        "project",
        "bug_id",
        "status",
        "start_time",
        "end_time",
        "wall_sec",
        "return_code",
        "mutant_count",
        "test_count",
        "trigger_count",
        "matrix_validation",
        "failure_reason",
        "tool_versions",
        "parser_schema",
    ]
    tmp = path.with_suffix(".csv.tmp")
    rows = [state[k] for k in sorted(state)]
    with tmp.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def run_one(root: Path, project: str, bid: str) -> dict:
    out = root / "results" / "raw" / "t5" / f"{project}-{bid}"
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    start_iso = utcnow()
    # Host envelope slightly above scientific 1800s so GNU timeout inside the
    # container remains authoritative; host kill-after prevents orphan Java.
    host_cap = TIMEOUT_SEC + 60
    cname = f"mcn-full-{project}-{bid}"
    subprocess.run(["docker", "rm", "-f", cname], check=False, capture_output=True)
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        cname,
        "--network",
        "none",
        "-e",
        "D4J_HOME=/opt/defects4j",
        "-e",
        f"WORKDIR=/work/checkout/{project}-{bid}f",
        "-v",
        f"{root}:/opt/artifact",
        IMAGE,
        "bash",
        "-lc",
        (
            "timeout --kill-after=30 %d /opt/artifact/scripts/t5_one_bug.sh %s %s /opt/artifact "
            "/opt/artifact/results/raw/t5; echo $? > /opt/artifact/results/raw/t5/%s-%s/campaign.exit"
            % (TIMEOUT_SEC, project, bid, project, bid)
        ),
    ]
    cmd = ["timeout", "--kill-after=60", str(host_cap), *docker_cmd]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end = time.time()
    subprocess.run(["docker", "rm", "-f", cname], check=False, capture_output=True)
    camp = out / "campaign.exit"
    if camp.is_file():
        try:
            rc = int(camp.read_text().strip().split()[-1])
        except ValueError:
            rc = proc.returncode
    else:
        rc = proc.returncode
    # Container timeout (124) or host envelope kill → scientific TIMEOUT.
    # Do not discard COMPLETE_VALID solely because wall ≈ 1800.
    wall = end - start
    maps_ok = all((out / n).is_file() for n in MAPS)
    if rc == 124 or (wall >= (TIMEOUT_SEC + 55) and not maps_ok):
        (out / "exclusion.txt").write_text("timeout\n")
        status = "TIMEOUT"
        reason = "timeout"
        rc = 124
    else:
        status = classify_dir(out)
        reason = "" if status == "COMPLETE_VALID" else status
    mut_n = count_lines(out / "mutants.log")
    test_n = count_lines(out / "testMap.csv")
    trig_n = None
    tf = out / "trigger_tests.txt"
    if tf.is_file():
        trig_n = sum(1 for ln in tf.read_text(errors="replace").splitlines() if ln.startswith("--- "))
    valid = "PASS" if status == "COMPLETE_VALID" else "FAIL"
    rec = {
        "project": project,
        "bug_id": bid,
        "status": status,
        "start_time": start_iso,
        "end_time": utcnow(),
        "wall_sec": "%.1f" % (end - start),
        "return_code": str(rc),
        "mutant_count": "" if mut_n is None else str(mut_n),
        "test_count": "" if test_n is None else str(test_n),
        "trigger_count": "" if trig_n is None else str(trig_n),
        "matrix_validation": valid,
        "failure_reason": reason,
        "tool_versions": "defects4j=3.0.1;major=3.0.1;java=11",
        "parser_schema": "SCHEMA_V1",
    }
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{out}:/d",
            IMAGE,
            "chown",
            "-R",
            "1000:1000",
            "/d",
        ],
        check=False,
        capture_output=True,
    )
    log = out / "campaign.log"
    log.write_text(
        "rc=%s status=%s wall=%s\nstdout_bytes=%d stderr_bytes=%d\n"
        % (rc, status, rec["wall_sec"], len(proc.stdout or ""), len(proc.stderr or ""))
    )
    return rec


def seed_existing(root: Path, manifest_rows: list[dict], state: dict) -> None:
    for rec in manifest_rows:
        key = (rec["project"], rec["bug_id"])
        if key in state and state[key].get("status") not in ("", "PENDING", "RUNNING"):
            continue
        st = rec["terminal_status"]
        if st in ("PENDING",):
            state[key] = {
                "project": rec["project"],
                "bug_id": rec["bug_id"],
                "status": "PENDING",
                "start_time": "",
                "end_time": "",
                "wall_sec": "",
                "return_code": "",
                "mutant_count": "",
                "test_count": "",
                "trigger_count": "",
                "matrix_validation": "",
                "failure_reason": "",
                "tool_versions": "defects4j=3.0.1;major=3.0.1;java=11",
                "parser_schema": "SCHEMA_V1",
            }
        else:
            d = root / "results" / "raw" / "t5" / f"{rec['project']}-{rec['bug_id']}"
            mut_n = count_lines(d / "mutants.log")
            test_n = count_lines(d / "testMap.csv")
            trig_n = ""
            tf = d / "trigger_tests.txt"
            if tf.is_file():
                trig_n = str(
                    sum(1 for ln in tf.read_text(errors="replace").splitlines() if ln.startswith("--- "))
                )
            state[key] = {
                "project": rec["project"],
                "bug_id": rec["bug_id"],
                "status": st,
                "start_time": "",
                "end_time": "",
                "wall_sec": "",
                "return_code": "",
                "mutant_count": "" if mut_n is None else str(mut_n),
                "test_count": "" if test_n is None else str(test_n),
                "trigger_count": trig_n,
                "matrix_validation": "PASS" if st == "COMPLETE_VALID" else "FAIL",
                "failure_reason": "" if st == "COMPLETE_VALID" else st,
                "tool_versions": "defects4j=3.0.1;major=3.0.1;java=11",
                "parser_schema": "SCHEMA_V1",
            }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fs = root / "results" / "derived" / "full_study"
    fs.mkdir(parents=True, exist_ok=True)
    man_path = fs / "population_manifest.csv"
    state_path = fs / "campaign_state.csv"
    with man_path.open() as fh:
        manifest = list(csv.DictReader(fh))
    state = load_state(state_path)
    seed_existing(root, manifest, state)
    raw = root / "results" / "raw" / "t5"
    for key, rec in list(state.items()):
        if rec.get("status") == "RUNNING":
            st = classify_dir(raw / f"{key[0]}-{key[1]}")
            rec["status"] = st if st == "COMPLETE_VALID" else "PENDING"
    write_state(state_path, state)

    todo = []
    for rec in manifest:
        key = (rec["project"], rec["bug_id"])
        st = state[key]["status"]
        if rec["needs_execution"] == "YES" and st in ("PENDING", "RUNNING"):
            todo.append(rec)
        elif st == "PENDING" and rec["pre_outcome_eligible"] == "YES" and rec["already_attempted"] == "NO":
            todo.append(rec)

    (fs / "campaign_todo.json").write_text(
        json.dumps(
            {
                "n_todo": len(todo),
                "max_parallel": MAX_PARALLEL,
                "timeout_sec": TIMEOUT_SEC,
                "note": "Acquisition does not compute aggregate excess coupling.",
            },
            indent=2,
        )
        + "\n"
    )
    print("todo=%d parallel=%d" % (len(todo), MAX_PARALLEL), flush=True)
    if not todo:
        return 0

    lock_note = fs / "acquisition_started.txt"
    if not lock_note.is_file():
        lock_note.write_text("started=%s\n" % utcnow())

    def job(rec):
        key = (rec["project"], rec["bug_id"])
        with STATE_LOCK:
            state[key]["status"] = "RUNNING"
            state[key]["start_time"] = utcnow()
            write_state(state_path, state)
        result = run_one(root, rec["project"], rec["bug_id"])
        with STATE_LOCK:
            state[key] = result
            write_state(state_path, state)
        print(
            "%s %s-%s %s wall=%s"
            % (utcnow(), rec["project"], rec["bug_id"], result["status"], result["wall_sec"]),
            flush=True,
        )
        return result

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futs = [ex.submit(job, rec) for rec in todo]
        for fut in as_completed(futs):
            fut.result()
    n_done = sum(1 for v in state.values() if v["status"] == "COMPLETE_VALID")
    print("complete_valid=%d" % n_done, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
