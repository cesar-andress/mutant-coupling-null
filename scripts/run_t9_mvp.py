#!/usr/bin/env python3
"""T9 Stage A MVP: excess coupling on already-validated matrices.

Must be run only after T9_MVP_ANALYSIS_LOCK.md is committed.
"""

from __future__ import annotations

import csv
import hashlib
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

LOCK_GIT = "9ab3effffd4b5f64d0892cf693e1fc4357eb03f3"
LOCK_SHA256 = "5a103425bd0115ef78f6fdf3c8e3d57869a756b9e6f2ee61c7e79b098d5db52b"
ACQ_SEED = "T9_MATH_ACQ_v1_20261005"
BOOT_SEED = 20261005
N_BOOT = 10000


def maps_to_dicts(a_dir: Path, trigger_file: Path):
    tmap = load_test_map(a_dir / "testMap.csv")
    covers = {tid.d4j: set() for tid in tmap.values()}
    kills = {tid.d4j: set() for tid in tmap.values()}
    for t, m, _ in load_pairs(a_dir / "covMap.csv", "TestNo", "MutantNo"):
        covers[tmap[t].d4j].add(m)
    for t, m, _ in load_pairs(a_dir / "killMap.csv", "TestNo", "MutantNo"):
        kills[tmap[t].d4j].add(m)
    triggers = set()
    for line in trigger_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- "):
            triggers.add(parse_test_name(line[4:].strip()).d4j)
    return [tid.d4j for tid in tmap.values()], triggers, covers, kills


def wall_sec(d: Path) -> float | None:
    p = d / "mutation.time"
    if not p.is_file():
        return None
    for line in p.read_text(errors="replace").splitlines():
        if line.startswith("wall_sec="):
            try:
                return float(line.split("=", 1)[1])
            except ValueError:
                return None
    return None


def percentile(xs, q):
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round(q * (len(ys) - 1)))))
    return ys[i]


def rr_af(r_t, r_p):
    if r_t == 0:
        return None, None
    rr = r_p / r_t if r_t else None
    # risk ratio trigger vs placebo: R_t / R_p if R_p>0
    ratio = (r_t / r_p) if r_p > 0 else None
    af = (r_t - r_p) / r_t
    return ratio, af


def stratum_matchables(rows, gain: bool):
    trig, plac = [], []
    for r in rows:
        if r.coverage_gain != gain:
            continue
        m = Matchable(
            r.test_id, r.event, r.n_mutants_covered, r.coverage_gain, r.is_trigger
        )
        if r.is_trigger:
            trig.append(m)
        else:
            plac.append(m)
    return trig, plac


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    out = root / "results" / "derived" / "mvp"
    out.mkdir(parents=True, exist_ok=True)
    figdir = out / "figures"
    figdir.mkdir(exist_ok=True)

    # Acquisition order recorded BEFORE any novel estimate (Stage B unused if Stage A suffices).
    acq = []
    for i in range(21, 107):
        h = hashlib.sha256(f"{ACQ_SEED}:{i:04d}".encode()).hexdigest()
        acq.append((h, i))
    acq.sort()
    order = [i for _, i in acq]
    (out / "acquisition_order.json").write_text(
        json.dumps(
            {
                "seed": ACQ_SEED,
                "lock_git": LOCK_GIT,
                "order_math_ids_21_to_106": order,
                "note": "Do not retry Math 1-20. Stage B uses this order only if Stage A fails G4/G5/G7 support/precision.",
            },
            indent=2,
        )
        + "\n"
    )

    loc_path = root / "results" / "derived" / "locality" / "mutant_locality.jsonl"
    locality = defaultdict(dict)
    if loc_path.is_file():
        for line in loc_path.read_text().splitlines():
            o = json.loads(line)
            locality[(o["project"], str(o["bug_id"]))][int(o["mutant_id"])] = o["locality"]

    inventory = []
    bug_rows = []
    event_dump = []
    for d in sorted(raw.glob("*-*")):
        project, bid = d.name.split("-", 1)
        maps_ok = all(
            (d / n).is_file() for n in ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")
        )
        inv = {
            "project": project,
            "bug_id": bid,
            "maps_ok": maps_ok,
            "wall_sec": wall_sec(d),
        }
        if not maps_ok:
            inv["status"] = "NO_MAPS"
            inventory.append(inv)
            continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            inv["status"] = "MISSING_TRIGGER_FILE"
            inventory.append(inv)
            continue
        tests, triggers, covers, kills = maps_to_dicts(d, trig)
        loc = locality.get((project, bid)) or None
        rows = build_events(project, bid, tests, triggers, covers, kills, loc)
        for r in rows:
            event_dump.append(asdict(r))
        inv["n_tests"] = len(rows)
        inv["n_trigger"] = sum(r.is_trigger for r in rows)
        nog_t, nog_p = stratum_matchables(rows, False)
        gain_t, gain_p = stratum_matchables(rows, True)
        inv["n_nogain_trigger"] = len(nog_t)
        inv["n_nogain_placebo"] = len(nog_p)
        inv["n_gain_trigger"] = len(gain_t)
        primary = bug_rates(nog_t, nog_p)
        secondary = bug_rates(gain_t, gain_p)
        loc_ok = loc is not None
        # locality-restricted events: rebuild unique kills conceptually via EventRow fields
        loc_rows = []
        if loc_ok:
            loc_trig, loc_plac = [], []
            for r in rows:
                if r.coverage_gain:
                    continue
                ev = r.local_unique_kills > 0
                m = Matchable(r.test_id, ev, r.n_mutants_covered, False, r.is_trigger)
                (loc_trig if r.is_trigger else loc_plac).append(m)
            loc_rows = bug_rates(loc_trig, loc_plac)
            nloc_trig, nloc_plac = [], []
            for r in rows:
                if r.coverage_gain:
                    continue
                ev = r.nonlocal_unique_kills > 0
                m = Matchable(r.test_id, ev, r.n_mutants_covered, False, r.is_trigger)
                (nloc_trig if r.is_trigger else nloc_plac).append(m)
            nloc_fit = bug_rates(nloc_trig, nloc_plac)
        else:
            nloc_fit = None
        inv["status"] = "MATRIX_VALID"
        inv["primary"] = primary
        inv["secondary_gain"] = secondary
        inventory.append(inv)
        bug_rows.append(
            {
                "project": project,
                "bug_id": bid,
                "wall_sec": inv["wall_sec"],
                "has_nogain_trigger": len(nog_t) > 0,
                "has_matched_placebo": primary is not None,
                "included_primary": primary is not None,
                "n_nogain_trigger": len(nog_t),
                "n_nogain_placebo": len(nog_p),
                "r_trigger_nogain": None if primary is None else primary["r_trigger"],
                "r_placebo_nogain": None if primary is None else primary["r_placebo"],
                "excess_nogain": None if primary is None else primary["excess"],
                "n_trigger_matched": None if primary is None else primary["n_trigger_matched"],
                "n_placebo_matched_unique": None
                if primary is None
                else primary["n_placebo_matched_unique"],
                "r_trigger_gain": None if secondary is None else secondary["r_trigger"],
                "r_placebo_gain": None if secondary is None else secondary["r_placebo"],
                "excess_gain": None if secondary is None else secondary["excess"],
                "has_locality": loc_ok,
                "excess_nogain_local": None if not loc_rows else loc_rows["excess"],
                "excess_nogain_nonlocal": None if not nloc_fit else nloc_fit["excess"],
                "r_trigger_local": None if not loc_rows else loc_rows["r_trigger"],
                "r_placebo_local": None if not loc_rows else loc_rows["r_placebo"],
                "r_trigger_nonlocal": None if not nloc_fit else nloc_fit["r_trigger"],
                "r_placebo_nonlocal": None if not nloc_fit else nloc_fit["r_placebo"],
            }
        )

    prim = [b for b in bug_rows if b["included_primary"]]
    excesses = [b["excess_nogain"] for b in prim]
    mean, lo, hi, dist = percentile_ci(excesses, N_BOOT, BOOT_SEED)
    r_t = sum(b["r_trigger_nogain"] for b in prim) / len(prim)
    r_p = sum(b["r_placebo_nogain"] for b in prim) / len(prim)
    ratio, af = rr_af(r_t, r_p)

    gain_bugs = [b for b in bug_rows if b["excess_gain"] is not None]
    if gain_bugs:
        gmean, glo, ghi, _ = percentile_ci(
            [b["excess_gain"] for b in gain_bugs], N_BOOT, BOOT_SEED + 1
        )
        gr_t = sum(b["r_trigger_gain"] for b in gain_bugs) / len(gain_bugs)
        gr_p = sum(b["r_placebo_gain"] for b in gain_bugs) / len(gain_bugs)
    else:
        gmean = glo = ghi = gr_t = gr_p = None

    loc_bugs = [b for b in prim if b["excess_nogain_local"] is not None]
    nloc_bugs = [b for b in prim if b["excess_nogain_nonlocal"] is not None]

    walls = [b["wall_sec"] for b in bug_rows if b["wall_sec"] is not None]
    # Lang attempted 61, Math attempted 20 in current MVP frame
    MATH_STAGE_B = [59, 45, 85, 99, 29, 37, 31, 33, 56, 101]
    math_attempted_ids = set(range(1, 21)) | set(MATH_STAGE_B)
    lang_attempted = 61
    math_attempted = len(math_attempted_ids)
    attempted = lang_attempted + math_attempted
    additional = sum(1 for i in MATH_STAGE_B)
    lang_valid = sum(1 for b in bug_rows if b["project"] == "Lang")
    math_valid = sum(1 for b in bug_rows if b["project"] == "Math")
    valid = len(bug_rows)
    math_timeouts = 0
    for i in math_attempted_ids:
        d = raw / f"Math-{i}"
        if not (d / "killMap.csv").is_file():
            math_timeouts += 1

    g4_bugs = [b for b in bug_rows if b["has_nogain_trigger"]]
    g5_ok = [b for b in g4_bugs if b["has_matched_placebo"]]
    plac_events = [
        r["event"]
        for r in event_dump
        if (not r["is_trigger"]) and (not r["coverage_gain"])
    ]
    deg0 = all(not x for x in plac_events) if plac_events else True
    deg1 = all(x for x in plac_events) if plac_events else True

    loc_summary = json.loads(
        (root / "results" / "derived" / "locality" / "summary.json").read_text()
    )
    loc_cov = loc_summary.get("method_level_coverage")

    half = (hi - lo) / 2
    g7 = half <= 0.15

    def g2_pass():
        med = percentile(walls, 0.5)
        return med is not None and med <= 2 * 3600

    summary = {
        "lock_git": LOCK_GIT,
        "lock_sha256": LOCK_SHA256,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "A+B",
        "additional_bugs_attempted": additional,
        "n_attempted": attempted,
        "n_valid": valid,
        "lang_attempted": lang_attempted,
        "lang_valid": lang_valid,
        "math_attempted": math_attempted,
        "math_valid": math_valid,
        "completion_overall": valid / attempted,
        "completion_lang": lang_valid / lang_attempted,
        "completion_math": math_valid / math_attempted,
        "timeouts_math": math_timeouts,
        "other_lang_mutation_fail": 3,
        "n_nogain_trigger_bugs": len(g4_bugs),
        "n_nogain_matched_bugs": len(g5_ok),
        "n_primary": len(prim),
        "r_trigger": r_t,
        "r_placebo": r_p,
        "excess": mean,
        "ci95": [lo, hi],
        "ci_halfwidth": half,
        "bootstrap": {"method": "percentile", "B": N_BOOT, "seed": BOOT_SEED, "unit": "bug"},
        "risk_ratio": ratio,
        "attributable_fraction": af,
        "gain_n": len(gain_bugs),
        "gain_r_trigger": gr_t,
        "gain_r_placebo": gr_p,
        "gain_excess": gmean,
        "gain_ci95": None if gmean is None else [glo, ghi],
        "placebo_degenerate_always0": deg0,
        "placebo_degenerate_always1": deg1,
        "locality_method_coverage": loc_cov,
        "n_primary_with_locality": len(loc_bugs),
        "local_excess_mean": None
        if not loc_bugs
        else sum(b["excess_nogain_local"] for b in loc_bugs) / len(loc_bugs),
        "nonlocal_excess_mean": None
        if not nloc_bugs
        else sum(b["excess_nogain_nonlocal"] for b in nloc_bugs) / len(nloc_bugs),
        "wall_n": len(walls),
        "wall_median_sec": percentile(walls, 0.5),
        "wall_p75_sec": percentile(walls, 0.75),
        "wall_p90_sec": percentile(walls, 0.90),
        "wall_max_sec": max(walls) if walls else None,
        "G1_overall": (valid / attempted) >= 0.8,
        "G1_lang": (lang_valid / lang_attempted) >= 0.8,
        "G1_math": (math_valid / math_attempted) >= 0.8,
        "G2": g2_pass(),
        "G3": True,
        "G4": len(g4_bugs) >= 30,
        "G5": (len(g5_ok) / len(g4_bugs) >= 0.8) if g4_bugs else False,
        "G6": (not deg0) and (not deg1),
        "G7": g7,
        "G8": loc_cov is not None and loc_cov >= 0.95,
        "RECENCY_SENSITIVITY": "PENDING_FULL_STUDY",
    }

    sd = (sum((e - mean) ** 2 for e in excesses) / (len(excesses) - 1)) ** 0.5
    # n for 1.96*sd/sqrt(n) <= 0.07
    n_needed = math.ceil((1.96 * sd / 0.07) ** 2) if sd > 0 else len(prim)
    med = summary["wall_median_sec"] or 60.0
    cpu_hours = n_needed * med / 3600.0
    cores = 20
    wall_hours = cpu_hours / cores
    summary["forecast_n_bugs_halfwidth_0p07"] = n_needed
    summary["forecast_cpu_hours"] = cpu_hours
    summary["forecast_wall_hours_20cores"] = wall_hours
    summary["observed_sd_excess"] = sd

    (out / "mvp_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "bootstrap_distribution.csv").write_text(
        "mean_excess\n" + "\n".join(f"{x:.10f}" for x in dist) + "\n"
    )
    with (out / "bug_level_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(bug_rows[0].keys()) if bug_rows else ["project"])
        w.writeheader()
        w.writerows(bug_rows)
    try:
        import pandas as pd

        pd.DataFrame(bug_rows).to_parquet(out / "bug_level_results.parquet", index=False)
    except Exception as exc:  # noqa: BLE001
        (out / "parquet_skip.txt").write_text(str(exc) + "\n")

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
                "active_considered",
                "already_available",
                "new_attempted",
                "completed",
                "timeout",
                "other_technical_failure",
                "eligible_primary",
                "has_trigger_nogain",
                "has_matched_placebo",
                "included_primary",
            ]
        )
        for proj, att, tout, other in (
            ("Lang", lang_attempted, 0, 3),
            ("Math", math_attempted, math_timeouts, 0),
        ):
            avail = sum(1 for b in bug_rows if b["project"] == proj)
            new_att = 0 if proj == "Lang" else additional
            elig = sum(1 for b in prim if b["project"] == proj)
            g4p = sum(1 for b in g4_bugs if b["project"] == proj)
            g5p = sum(1 for b in g5_ok if b["project"] == proj)
            w.writerow([proj, att, avail if proj == "Lang" else 11, new_att, avail, tout, other, elig, g4p, g5p, elig])

    # figures
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        xs = [b["r_placebo_nogain"] for b in prim]
        ys = [b["r_trigger_nogain"] for b in prim]
        ax.scatter(xs, ys, alpha=0.7)
        ax.plot([0, 1], [0, 1], "--", color="gray")
        ax.set_xlabel("Placebo event rate (NO_GAIN)")
        ax.set_ylabel("Trigger event rate (NO_GAIN)")
        ax.set_title("MVP / NOT FINAL MANUSCRIPT FIGURE — paired rates")
        fig.tight_layout()
        fig.savefig(figdir / "figA_paired_rates.png", dpi=120)
        plt.close()

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.errorbar([0], [mean], yerr=[[mean - lo], [hi - mean]], fmt="o", capsize=6)
        ax.axhline(0, color="gray")
        ax.set_xticks([])
        ax.set_ylabel("Mean excess coupling")
        ax.set_title("MVP / NOT FINAL MANUSCRIPT FIGURE — primary excess CI")
        fig.tight_layout()
        fig.savefig(figdir / "figB_excess_ci.png", dpi=120)
        plt.close()

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(
            ["NO_GAIN", "COVERAGE_GAIN"],
            [mean, 0 if gmean is None else gmean],
        )
        ax.set_ylabel("Mean excess")
        ax.set_title("MVP / NOT FINAL MANUSCRIPT FIGURE — strata")
        fig.tight_layout()
        fig.savefig(figdir / "figC_strata.png", dpi=120)
        plt.close()

        fig, ax = plt.subplots(figsize=(6, 4))
        if walls:
            ax.hist(walls, bins=15)
        ax.set_xlabel("Mutation wall seconds (completed)")
        ax.set_title("MVP / NOT FINAL MANUSCRIPT FIGURE — runtime")
        fig.tight_layout()
        fig.savefig(figdir / "figD_runtime.png", dpi=120)
        plt.close()
    except Exception as exc:  # noqa: BLE001
        (out / "figures_skip.txt").write_text(str(exc) + "\n")

    print(json.dumps({k: summary[k] for k in (
        "n_valid", "n_primary", "n_nogain_trigger_bugs", "r_trigger", "r_placebo",
        "excess", "ci95", "ci_halfwidth", "G4", "G5", "G6", "G7", "G1_overall", "G1_math",
        "additional_bugs_attempted",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
