#!/usr/bin/env python3
"""Freeze full-study population manifest (pre-outcome). No coupling estimates."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ACQ_SEED = "FULL_STUDY_ACQ_v1_20261005"
MAPS = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")


def classify(d: Path) -> str:
    if not d.is_dir():
        return "PENDING"
    maps_ok = all((d / n).is_file() for n in MAPS)
    trig_ok = (d / "trigger_tests.txt").is_file()
    if maps_ok and trig_ok:
        return "COMPLETE_VALID"
    excl = d / "exclusion.txt"
    if excl.is_file():
        t = excl.read_text(errors="replace").lower()
        if "timeout" in t:
            return "TIMEOUT"
        if "missing trigger" in t:
            return "OTHER_FAILURE"
    mut_exit = d / "mutation.exit"
    if mut_exit.is_file():
        try:
            rc = int(mut_exit.read_text().strip() or "1")
        except ValueError:
            rc = 1
        if rc != 0:
            return "MUTATION_FAILURE"
    # Watchdog timeout often leaves mutation logs without mutation.exit or exclusion.txt.
    if (d / "mutation.time").is_file() or (d / "mutation.stderr").is_file():
        if not maps_ok:
            return "TIMEOUT"
    for name, label in (
        ("compile.exit", "BUILD_FAILURE"),
        ("checkout.exit", "BUILD_FAILURE"),
    ):
        p = d / name
        if p.is_file():
            try:
                rc = int(p.read_text().strip() or "0")
            except ValueError:
                rc = 1
            if rc != 0:
                return label
    if (d / "DONE").is_file() and not maps_ok:
        return "OTHER_FAILURE"
    if any(d.iterdir()):
        return "OTHER_FAILURE"
    return "PENDING"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    active_src = Path("/tmp/d4j_active.csv")
    if len(__import__("sys").argv) > 1:
        active_src = Path(__import__("sys").argv[1])
    raw = root / "results" / "raw" / "t5"
    out_dir = root / "results" / "derived" / "full_study"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with active_src.open() as fh:
        for rec in csv.DictReader(fh):
            project = rec["project"]
            bid = rec["bug_id"]
            d = raw / f"{project}-{bid}"
            status = classify(d)
            valid = status == "COMPLETE_VALID"
            attempted = status != "PENDING"
            eligible = True
            reason = ""
            needs = "YES" if (eligible and not attempted) else "NO"
            h = hashlib.sha256(f"{ACQ_SEED}:{project}:{bid}".encode()).hexdigest()
            rows.append(
                {
                    "acq_hash": h,
                    "project": project,
                    "bug_id": bid,
                    "active": "YES",
                    "pre_outcome_eligible": "YES",
                    "pre_outcome_exclusion_reason": reason,
                    "already_attempted": "YES" if attempted else "NO",
                    "existing_valid_matrix": "YES" if valid else "NO",
                    "terminal_status": status,
                    "needs_execution": needs,
                }
            )
    rows.sort(key=lambda r: r["acq_hash"])
    fields = [
        "acq_hash",
        "project",
        "bug_id",
        "active",
        "pre_outcome_eligible",
        "pre_outcome_exclusion_reason",
        "already_attempted",
        "existing_valid_matrix",
        "terminal_status",
        "needs_execution",
    ]
    path = out_dir / "population_manifest.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    n_el = sum(1 for r in rows if r["pre_outcome_eligible"] == "YES")
    n_valid = sum(1 for r in rows if r["existing_valid_matrix"] == "YES")
    n_need = sum(1 for r in rows if r["needs_execution"] == "YES")
    n_att = sum(1 for r in rows if r["already_attempted"] == "YES")
    summary = out_dir / "population_freeze_summary.csv"
    with summary.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        w.writerow(["active_bugs", n])
        w.writerow(["pre_outcome_eligible", n_el])
        w.writerow(["already_attempted", n_att])
        w.writerow(["existing_valid_matrix", n_valid])
        w.writerow(["needs_execution", n_need])
        w.writerow(["acq_seed", ACQ_SEED])
    print(
        "active=%d eligible=%d attempted=%d valid=%d needs=%d"
        % (n, n_el, n_att, n_valid, n_need)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
