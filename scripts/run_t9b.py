#!/usr/bin/env python3
"""T9b precision checkpoints. Same analysis as T9; writes mvp_t9b/ only."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from killmap.parse import load_pairs, load_test_map, parse_test_name  # noqa: E402
from mvp.bootstrap import percentile_ci  # noqa: E402
from mvp.matching import Matchable, bug_rates  # noqa: E402
from placebo.engine import build_events  # noqa: E402

# Import helpers from T9 runner without executing main.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "run_t9_mvp", Path(__file__).resolve().parents[1] / "scripts" / "run_t9_mvp.py"
)
_t9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t9)  # type: ignore[union-attr]

LOCK_T9B_GIT = "c9947a5c0fe29bbbfcfad776a35821db38cacae2"
LOCK_T9B_SHA = "c8916b93fbda05293667bbc1a8508d5233411be695caa798abb47a7f39fae44a"
T9_STAGE_B = [59, 45, 85, 99, 29, 37, 31, 33, 56, 101]
T9B_ORDER_REMAINING = [
    81, 77, 53, 49, 89, 48, 27, 92, 66, 41,
    83, 67, 28, 64, 54, 50, 26, 88, 23, 70,
    84, 60, 98, 93, 39, 91, 30, 58, 97, 95,
    43, 100, 102, 25, 38, 57, 68, 32, 104, 87,
]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    extra = [int(x) for x in sys.argv[2:]]
    raw = root / "results" / "raw" / "t5"
    out = root / "results" / "derived" / "mvp_t9b"
    out.mkdir(parents=True, exist_ok=True)

    math_attempted_ids = set(range(1, 21)) | set(T9_STAGE_B) | set(extra)
    loc_path = root / "results" / "derived" / "locality" / "mutant_locality.jsonl"
    locality = defaultdict(dict)
    if loc_path.is_file():
        for line in loc_path.read_text().splitlines():
            o = json.loads(line)
            locality[(o["project"], str(o["bug_id"]))][int(o["mutant_id"])] = o["locality"]

    bug_rows = []
    event_dump = []
    for d in sorted(raw.glob("*-*")):
        project, bid = d.name.split("-", 1)
        maps_ok = all(
            (d / n).is_file() for n in ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")
        )
        if not maps_ok:
            continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            continue
        tests, triggers, covers, kills = _t9.maps_to_dicts(d, trig)
        loc = locality.get((project, bid)) or None
        rows = build_events(project, bid, tests, triggers, covers, kills, loc)
        for r in rows:
            event_dump.append(asdict(r))
        nog_t, nog_p = _t9.stratum_matchables(rows, False)
        gain_t, gain_p = _t9.stratum_matchables(rows, True)
        primary = bug_rates(nog_t, nog_p)
        secondary = bug_rates(gain_t, gain_p)
        loc_fit = nloc_fit = None
        if loc is not None:
            lt, lp, nt, np_ = [], [], [], []
            for r in rows:
                if r.coverage_gain:
                    continue
                lm = Matchable(r.test_id, r.local_unique_kills > 0, r.n_mutants_covered, False, r.is_trigger)
                nm = Matchable(r.test_id, r.nonlocal_unique_kills > 0, r.n_mutants_covered, False, r.is_trigger)
                (lt if r.is_trigger else lp).append(lm)
                (nt if r.is_trigger else np_).append(nm)
            loc_fit = bug_rates(lt, lp)
            nloc_fit = bug_rates(nt, np_)
        bug_rows.append(
            {
                "project": project,
                "bug_id": bid,
                "wall_sec": _t9.wall_sec(d),
                "has_nogain_trigger": len(nog_t) > 0,
                "has_matched_placebo": primary is not None,
                "included_primary": primary is not None,
                "n_nogain_trigger": len(nog_t),
                "n_nogain_placebo": len(nog_p),
                "r_trigger_nogain": None if primary is None else primary["r_trigger"],
                "r_placebo_nogain": None if primary is None else primary["r_placebo"],
                "excess_nogain": None if primary is None else primary["excess"],
                "r_trigger_gain": None if secondary is None else secondary["r_trigger"],
                "r_placebo_gain": None if secondary is None else secondary["r_placebo"],
                "excess_gain": None if secondary is None else secondary["excess"],
                "has_locality": loc is not None,
                "excess_nogain_local": None if not loc_fit else loc_fit["excess"],
                "excess_nogain_nonlocal": None if not nloc_fit else nloc_fit["excess"],
            }
        )

    prim = [b for b in bug_rows if b["included_primary"]]
    excesses = [b["excess_nogain"] for b in prim]
    mean, lo, hi, dist = _t9.percentile_ci(excesses, _t9.N_BOOT, _t9.BOOT_SEED)
    r_t = sum(b["r_trigger_nogain"] for b in prim) / len(prim)
    r_p = sum(b["r_placebo_nogain"] for b in prim) / len(prim)
    ratio, af = _t9.rr_af(r_t, r_p)
    gain_bugs = [b for b in bug_rows if b["excess_gain"] is not None]
    if gain_bugs:
        gmean, glo, ghi, _ = _t9.percentile_ci(
            [b["excess_gain"] for b in gain_bugs], _t9.N_BOOT, _t9.BOOT_SEED + 1
        )
    else:
        gmean = glo = ghi = None
    walls = [b["wall_sec"] for b in bug_rows if b["wall_sec"] is not None]
    lang_valid = sum(1 for b in bug_rows if b["project"] == "Lang")
    math_valid = sum(1 for b in bug_rows if b["project"] == "Math")
    lang_attempted = 61
    math_attempted = len(math_attempted_ids)
    attempted = lang_attempted + math_attempted
    valid = len(bug_rows)
    math_timeouts = sum(
        1 for i in math_attempted_ids if not (raw / f"Math-{i}" / "killMap.csv").is_file()
    )
    g4_bugs = [b for b in bug_rows if b["has_nogain_trigger"]]
    g5_ok = [b for b in g4_bugs if b["has_matched_placebo"]]
    plac_events = [
        r["event"] for r in event_dump if (not r["is_trigger"]) and (not r["coverage_gain"])
    ]
    deg0 = all(not x for x in plac_events) if plac_events else True
    deg1 = all(bool(x) for x in plac_events) if plac_events else True
    loc_cov = json.loads((root / "results/derived/locality/summary.json").read_text())[
        "method_level_coverage"
    ]
    half = (hi - lo) / 2
    summary = {
        "t9b_lock_git": LOCK_T9B_GIT,
        "t9b_lock_sha256": LOCK_T9B_SHA,
        "t9_original_halfwidth": 0.17237403401196502,
        "t9_original_verdict": "REVISE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "t9b_extra_ids": extra,
        "n_attempted": attempted,
        "n_valid": valid,
        "lang_valid": lang_valid,
        "math_valid": math_valid,
        "lang_attempted": lang_attempted,
        "math_attempted": math_attempted,
        "completion_overall": valid / attempted,
        "completion_lang": lang_valid / lang_attempted,
        "completion_math": math_valid / math_attempted,
        "timeouts_math": math_timeouts,
        "other_lang_mutation_fail": 3,
        "n_nogain_trigger_bugs": len(g4_bugs),
        "n_nogain_matched_bugs": len(g5_ok),
        "n_primary": len(prim),
        "primary_lang": sum(1 for b in prim if b["project"] == "Lang"),
        "primary_math": sum(1 for b in prim if b["project"] == "Math"),
        "r_trigger": r_t,
        "r_placebo": r_p,
        "excess": mean,
        "ci95": [lo, hi],
        "ci_halfwidth": half,
        "risk_ratio": ratio,
        "attributable_fraction": af,
        "gain_n": len(gain_bugs),
        "gain_excess": gmean,
        "gain_ci95": None if gmean is None else [glo, ghi],
        "placebo_degenerate_always0": deg0,
        "placebo_degenerate_always1": deg1,
        "locality_method_coverage": loc_cov,
        "wall_median_sec": _t9.percentile(walls, 0.5),
        "wall_p75_sec": _t9.percentile(walls, 0.75),
        "wall_p90_sec": _t9.percentile(walls, 0.90),
        "wall_max_sec": max(walls) if walls else None,
        "G1_overall": (valid / attempted) >= 0.8,
        "G1_lang": (lang_valid / lang_attempted) >= 0.8,
        "G1_math": (math_valid / math_attempted) >= 0.8,
        "G2": (_t9.percentile(walls, 0.5) or 0) <= 2 * 3600,
        "G3": True,
        "G4": len(g4_bugs) >= 30,
        "G5": (len(g5_ok) / len(g4_bugs) >= 0.8) if g4_bugs else False,
        "G6": (not deg0) and (not deg1),
        "G7": half <= 0.150,
        "G8": loc_cov >= 0.95,
        "observed_sd_excess": (
            (sum((e - mean) ** 2 for e in excesses) / (len(excesses) - 1)) ** 0.5
            if len(excesses) > 1
            else None
        ),
    }
    g_all = all(summary[k] for k in ("G1_overall", "G2", "G3", "G4", "G5", "G6", "G7", "G8"))
    # G1 Math separately reported; GO uses overall G1 as in T9 report item 31.
    summary["gates_for_stop"] = g_all
    (out / "mvp_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    import pandas as pd

    pd.DataFrame(bug_rows).to_parquet(out / "bug_level_results.parquet", index=False)
    with (out / "bug_level_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(bug_rows[0].keys()))
        w.writeheader()
        w.writerows(bug_rows)
    with (out / "compute_cost.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["project", "bug_id", "wall_sec"])
        w.writeheader()
        for b in bug_rows:
            w.writerow({"project": b["project"], "bug_id": b["bug_id"], "wall_sec": b["wall_sec"]})
    with (out / "sample_flow.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "project",
                "attempted",
                "completed",
                "timeout",
                "other_fail",
                "primary",
                "nogain_trigger",
                "matched_placebo",
            ]
        )
        w.writerow(
            [
                "Lang",
                lang_attempted,
                lang_valid,
                0,
                3,
                sum(1 for b in prim if b["project"] == "Lang"),
                sum(1 for b in g4_bugs if b["project"] == "Lang"),
                sum(1 for b in g5_ok if b["project"] == "Lang"),
            ]
        )
        w.writerow(
            [
                "Math",
                math_attempted,
                math_valid,
                math_timeouts,
                0,
                sum(1 for b in prim if b["project"] == "Math"),
                sum(1 for b in g4_bugs if b["project"] == "Math"),
                sum(1 for b in g5_ok if b["project"] == "Math"),
            ]
        )
    print(
        json.dumps(
            {
                "extra": extra,
                "n_primary": len(prim),
                "halfwidth": half,
                "G7": summary["G7"],
                "G1_overall": summary["G1_overall"],
                "G4": summary["G4"],
                "G5": summary["G5"],
                "G6": summary["G6"],
                "excess": mean,
                "ci95": [lo, hi],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
