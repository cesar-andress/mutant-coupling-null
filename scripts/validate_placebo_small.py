#!/usr/bin/env python3
"""ENGINEERING_VALIDATION_ONLY: events for a small deterministic bug set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from killmap.parse import load_mutants_log, load_pairs, load_test_map, parse_test_name  # noqa: E402
from placebo.engine import build_events  # noqa: E402


def maps_to_dicts(a_dir: Path, trigger_file: Path):
    tmap = load_test_map(a_dir / "testMap.csv")
    covers = {tid.d4j: set() for tid in tmap.values()}
    kills = {tid.d4j: set() for tid in tmap.values()}
    for t, m, _ in load_pairs(a_dir / "covMap.csv", "TestNo", "MutantNo"):
        covers[tmap[t].d4j].add(m)
    for t, m, _ in load_pairs(a_dir / "killMap.csv", "TestNo", "MutantNo"):
        kills[tmap[t].d4j].add(m)
    triggers = set()
    for line in trigger_file.read_text().splitlines():
        if line.startswith("--- "):
            triggers.add(parse_test_name(line[4:].strip()).d4j)
    return [tid.d4j for tid in tmap.values()], triggers, covers, kills


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    bugs = ["Lang-1", "Lang-3", "Lang-4", "Lang-5", "Lang-6"]
    out = root / "results" / "derived" / "placebo_validation"
    out.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for name in bugs:
        d = root / "results" / "raw" / "t5" / name
        project, bid = name.split("-", 1)
        trig = root / "external" / "defects4j" / "framework" / "projects" / project / "trigger_tests" / bid
        tests, triggers, covers, kills = maps_to_dicts(d, trig)
        loc = {}
        loc_path = root / "results" / "derived" / "locality" / "mutant_locality.jsonl"
        if loc_path.is_file():
            for line in loc_path.read_text().splitlines():
                o = json.loads(line)
                if o["project"] == project and o["bug_id"] == bid:
                    loc[int(o["mutant_id"])] = o["locality"]
        rows = build_events(project, bid, tests, triggers, covers, kills, loc or None)
        for r in rows:
            all_rows.append({**r.__dict__, "ENGINEERING_VALIDATION_ONLY": True})
    (out / "bug_test_events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in all_rows))
    # summary invariants
    inv = {
        "n_rows": len(all_rows),
        "triggers_never_eligible_placebo": all(
            (not r["is_trigger"]) or (not r["eligible_for_primary_placebo"]) for r in all_rows
        ),
        "event_eq_nunique_gt0": all(r["event"] == (r["n_unique_kills"] > 0) for r in all_rows),
        "ENGINEERING_VALIDATION_ONLY": True,
    }
    # degeneracy check on no-gain placebo
    nog = [r for r in all_rows if (not r["is_trigger"]) and (not r["coverage_gain"])]
    inv["nogain_placebo_n"] = len(nog)
    inv["nogain_placebo_event_rate"] = (sum(r["event"] for r in nog) / len(nog) if nog else None)
    inv["degenerate_always0"] = inv["nogain_placebo_event_rate"] == 0
    inv["degenerate_always1"] = inv["nogain_placebo_event_rate"] == 1
    (out / "summary.json").write_text(json.dumps(inv, indent=2) + "\n")
    print(json.dumps(inv))
    if inv["degenerate_always0"] or inv["degenerate_always1"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
