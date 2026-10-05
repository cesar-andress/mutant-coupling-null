#!/usr/bin/env python3
"""Build SCHEMA_V1 parquet tables from results/raw/t5/*/ maps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from etl.ingest import ingest_bug  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    out = root / "results" / "derived" / "schema_v1"
    pin = {}
    for line in (root / "env" / "pin.env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            pin[k] = v
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    all_bugs, all_tests, all_muts, all_cells = [], [], [], []
    last_prov = None
    for d in sorted(raw.glob("*-*")):
        if not (d / "killMap.csv").is_file():
            continue
        project, bid = d.name.split("-", 1)
        trig = root / "external" / "defects4j" / "framework" / "projects" / project / "trigger_tests" / bid
        if not trig.is_file():
            # inside container path
            trig = Path(f"/opt/defects4j/framework/projects/{project}/trigger_tests/{bid}")
        commit_row = None
        cdb = root / "external" / "defects4j" / "framework" / "projects" / project / "commit-db"
        if cdb.is_file():
            for line in cdb.read_text().splitlines():
                if line.startswith(bid + ","):
                    commit_row = line
                    break
        bugs, tests, muts, cells, prov = ingest_bug(
            project,
            bid,
            d,
            trig,
            pin.get("DEFECTS4J_REQUESTED_VERSION", "3.0.1"),
            pin.get("DEFECTS4J_SHA", ""),
            pin.get("MAJOR_VERSION", "3.0.1"),
            git_commit=git_commit,
            commit_db_row=commit_row,
        )
        all_bugs.append(bugs)
        all_tests.extend(tests)
        all_muts.extend(muts)
        all_cells.extend(cells)
        last_prov = prov
    if not all_bugs:
        print("no bugs ingested", file=sys.stderr)
        return 1
    import pandas as pd
    from dataclasses import asdict
    import json

    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_bugs).to_parquet(out / "bugs.parquet", index=False)
    pd.DataFrame(all_tests).to_parquet(out / "tests.parquet", index=False)
    pd.DataFrame(all_muts).to_parquet(out / "mutants.parquet", index=False)
    pd.DataFrame(all_cells).to_parquet(out / "cells.parquet", index=False)
    (out / "provenance.json").write_text(json.dumps(asdict(last_prov), indent=2) + "\n")
    print(
        json.dumps(
            {
                "bugs": len(all_bugs),
                "tests": len(all_tests),
                "mutants": len(all_muts),
                "cells": len(all_cells),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
