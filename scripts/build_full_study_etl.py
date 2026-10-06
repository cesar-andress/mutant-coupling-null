#!/usr/bin/env python3
"""Full-study SCHEMA_V1 ETL over all COMPLETE_VALID matrices. No outcome filtering."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from etl.ingest import ingest_bug  # noqa: E402
from killmap.parse import CanonicalIdCollisionError  # noqa: E402

MAPS = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    out = root / "results" / "derived" / "full_study"
    out.mkdir(parents=True, exist_ok=True)
    pin = {}
    pin_path = root / "env" / "pin.env"
    if pin_path.is_file():
        for line in pin_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                pin[k] = v
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    d4j_v = pin.get("DEFECTS4J_REQUESTED_VERSION", "3.0.1")
    d4j_sha = pin.get("DEFECTS4J_SHA", "6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09")
    major_v = pin.get("MAJOR_VERSION", "3.0.1")

    state = {}
    sp = out / "campaign_state.csv"
    if sp.is_file():
        with sp.open() as fh:
            for rec in csv.DictReader(fh):
                state[(rec["project"], rec["bug_id"])] = rec.get("status", "")

    all_bugs, all_tests, all_muts, all_cells = [], [], [], []
    qa_rows = []
    test_collisions = 0
    mutant_collisions = 0
    last_prov = None

    for d in sorted(raw.glob("*-*")):
        if not all((d / n).is_file() for n in MAPS):
            continue
        project, bid = d.name.split("-", 1)
        st = state.get((project, bid), "")
        if st and st not in ("COMPLETE_VALID", ""):
            # Prefer state when present; empty state still allow on-disk valid maps.
            if st != "COMPLETE_VALID":
                continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            continue
        try:
            bugs, tests, muts, cells, prov = ingest_bug(
                project,
                bid,
                d,
                trig,
                d4j_v,
                d4j_sha,
                major_v,
                git_commit=git_commit,
                commit_db_row=None,
            )
        except CanonicalIdCollisionError as exc:
            test_collisions += 1
            qa_rows.append(
                {
                    "project": project,
                    "bug_id": bid,
                    "status": "PARSER_FAILURE",
                    "detail": str(exc)[:200],
                }
            )
            continue
        except ValueError as exc:
            if "collision" in str(exc).lower():
                if "mutant" in str(exc).lower():
                    mutant_collisions += 1
                else:
                    test_collisions += 1
                qa_rows.append(
                    {
                        "project": project,
                        "bug_id": bid,
                        "status": "PARSER_FAILURE",
                        "detail": str(exc)[:200],
                    }
                )
                continue
            raise
        # Reconciliation
        n_tests_raw = max(0, sum(1 for _ in (d / "testMap.csv").open()) - 1)
        n_mut_raw = max(0, sum(1 for _ in (d / "mutants.log").open()) - 0)
        qa_rows.append(
            {
                "project": project,
                "bug_id": bid,
                "status": "OK",
                "n_tests_raw": n_tests_raw,
                "n_tests_canonical": len(tests),
                "n_mutants_raw": n_mut_raw,
                "n_mutants_canonical": len(muts),
                "n_cells": len(cells),
                "n_trigger": bugs["n_trigger"],
                "detail": "",
            }
        )
        if n_tests_raw != len(tests):
            qa_rows[-1]["status"] = "TEST_COUNT_MISMATCH"
        if n_mut_raw != len(muts):
            qa_rows[-1]["status"] = "MUTANT_COUNT_MISMATCH"
        # Record mismatches; still ingest if parse succeeded (no silent drop).
        all_bugs.append(bugs)
        all_tests.extend(tests)
        all_muts.extend(muts)
        all_cells.extend(cells)
        last_prov = prov

    import pandas as pd

    pd.DataFrame(all_bugs).to_parquet(out / "bugs.parquet", index=False)
    pd.DataFrame(all_tests).to_parquet(out / "tests.parquet", index=False)
    pd.DataFrame(all_muts).to_parquet(out / "mutants.parquet", index=False)
    pd.DataFrame(all_cells).to_parquet(out / "cells.parquet", index=False)
    with (out / "etl_qa.csv").open("w", newline="") as fh:
        fields = sorted({k for r in qa_rows for k in r})
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(qa_rows)
    summary = {
        "bugs": len(all_bugs),
        "tests": len(all_tests),
        "mutants": len(all_muts),
        "cells": len(all_cells),
        "canonical_test_id_collisions": test_collisions,
        "mutant_id_collisions": mutant_collisions,
        "schema_version": 1,
        "d4j_version": d4j_v,
        "d4j_sha": d4j_sha,
        "major_version": major_v,
        "git_commit": git_commit,
    }
    if last_prov is not None:
        (out / "etl_provenance.json").write_text(json.dumps(asdict(last_prov), indent=2) + "\n")
    (out / "etl_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if test_collisions == 0 and mutant_collisions == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
