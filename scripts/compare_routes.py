#!/usr/bin/env python3
"""Compare Route A maps with Route B per-test kill.csv files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, "/opt/artifact/src")

from killmap.parse import (  # noqa: E402
    compare_ab,
    load_mutants_log,
    load_test_map,
    parse_test_name,
    route_a_cells,
    route_b_cells_from_kill_csv,
)


def main() -> int:
    a_dir = Path(sys.argv[1])
    b_dir = Path(sys.argv[2])
    out = Path(sys.argv[3])
    tmap = load_test_map(a_dir / "testMap.csv")
    mutants = load_mutants_log(a_dir / "mutants.log")
    n_mut = max(mutants)
    a = route_a_cells(a_dir / "covMap.csv", a_dir / "killMap.csv", n_mut, tmap)
    b = {}
    missing_files = []
    for tid in tmap.values():
        p = b_dir / "per_test" / f"{tid.class_name}::{tid.method}".replace("::", "__") / "kill.csv"
        if not p.is_file():
            # class may be last component only in folder names if we used full class
            p = b_dir / "per_test" / f"{tid.class_name}__{tid.method}" / "kill.csv"
        if not p.is_file():
            missing_files.append(tid.d4j)
            continue
        one = route_b_cells_from_kill_csv(p)
        for mid, cell in one.items():
            b[(tid, mid)] = cell
    extra_b_tests = sorted({tid.d4j for tid, _ in b} - {t.d4j for t in tmap.values()})
    extra_a_tests = sorted({t.d4j for t in tmap.values()} - {tid.d4j for tid, _ in b})
    # Compare only tests present in both routes.
    b_f = {(tid, mid): v for (tid, mid), v in b.items() if tid in tmap.values()}
    report = compare_ab(a, b_f, tmap)
    report["n_mutants"] = n_mut
    report["n_tests_a"] = len(tmap)
    report["missing_route_b_files"] = missing_files
    report["extra_route_b_tests"] = extra_b_tests
    report["extra_route_a_tests"] = extra_a_tests
    report["method_level"] = all("[" in tmap[k].major for k in tmap)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in report if k != "details_head"}))
    if report["cell_mismatch"] or report["missing_in_b"] or missing_files:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
