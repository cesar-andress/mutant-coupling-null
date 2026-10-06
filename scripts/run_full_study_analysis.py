#!/usr/bin/env python3
"""Full-study analysis AFTER acquisition. Same event/matching/bootstrap as T9."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from killmap.parse import load_pairs, load_test_map, parse_test_name  # noqa: E402
from mvp.bootstrap import percentile_ci  # noqa: E402
from mvp.matching import Matchable, bug_rates  # noqa: E402
from placebo.engine import build_events  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "run_t9_mvp", Path(__file__).resolve().parents[1] / "scripts" / "run_t9_mvp.py"
)
_t9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t9)  # type: ignore[union-attr]

BOOT_SEED = 20261005
N_BOOT = 10000
LOCK_GIT = "75ad2fa3103103046e7a9241560496b95be6d078"
PRECISION_TARGET = 0.070
MAPS = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")


def maps_with_kill_filter(a_dir: Path, trigger_file: Path, allowed: set[str] | None):
    tmap = load_test_map(a_dir / "testMap.csv")
    covers = {tid.d4j: set() for tid in tmap.values()}
    kills = {tid.d4j: set() for tid in tmap.values()}
    for t, m, _ in load_pairs(a_dir / "covMap.csv", "TestNo", "MutantNo"):
        covers[tmap[t].d4j].add(m)
    for t, m, status in load_pairs(a_dir / "killMap.csv", "TestNo", "MutantNo"):
        if allowed is not None and status not in allowed:
            continue
        kills[tmap[t].d4j].add(m)
    triggers = set()
    for line in trigger_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- "):
            triggers.add(parse_test_name(line[4:].strip()).d4j)
    return [tid.d4j for tid in tmap.values()], triggers, covers, kills


def percentile(xs, q):
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round(q * (len(ys) - 1)))))
    return ys[i]


def rr_af(r_t, r_p):
    ratio = (r_t / r_p) if r_p and r_p > 0 else None
    af = ((r_t - r_p) / r_t) if r_t else None
    return ratio, af


def summarize_excess(values, seed):
    if not values:
        return None
    mean, lo, hi, dist = percentile_ci(values, N_BOOT, seed)
    return {
        "n": len(values),
        "mean": mean,
        "ci95": [lo, hi],
        "halfwidth": (hi - lo) / 2,
        "dist": dist,
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    out = root / "results" / "derived" / "full_study"
    figdir = out / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    loc_path = root / "results" / "derived" / "locality" / "mutant_locality.jsonl"
    locality = defaultdict(dict)
    n_loc_mut = 0
    if loc_path.is_file():
        for line in loc_path.read_text().splitlines():
            o = json.loads(line)
            locality[(o["project"], str(o["bug_id"]))][int(o["mutant_id"])] = o["locality"]
            n_loc_mut += 1

    state = {}
    sp = out / "campaign_state.csv"
    if sp.is_file():
        with sp.open() as fh:
            for rec in csv.DictReader(fh):
                state[(rec["project"], rec["bug_id"])] = rec

    man = []
    with (out / "population_manifest.csv").open() as fh:
        man = list(csv.DictReader(fh))

    bug_rows = []
    collisions_test = 0
    collisions_mut = 0
    fail_only_excess = []
    no_time_excess = []
    walls = []
    n_mutants_total = 0
    n_mutants_labeled = 0

    for rec in man:
        project, bid = rec["project"], rec["bug_id"]
        d = raw / f"{project}-{bid}"
        st = (state.get((project, bid)) or {}).get("status") or rec["terminal_status"]
        if st != "COMPLETE_VALID" and not all((d / n).is_file() for n in MAPS):
            continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            continue
        try:
            tests, triggers, covers, kills = maps_with_kill_filter(d, trig, None)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "collid" in msg or "collision" in msg:
                collisions_test += 1
            continue
        loc = locality.get((project, bid)) or None
        rows = build_events(project, bid, tests, triggers, covers, kills, loc)
        n_mut = len(set().union(*covers.values()) if covers else set())
        n_mutants_total += n_mut
        if loc:
            n_mutants_labeled += len(loc)
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
                mloc = Matchable(
                    r.test_id, r.local_unique_kills > 0, r.n_mutants_covered, False, r.is_trigger
                )
                (lt if r.is_trigger else lp).append(mloc)
                mnl = Matchable(
                    r.test_id,
                    r.nonlocal_unique_kills > 0,
                    r.n_mutants_covered,
                    False,
                    r.is_trigger,
                )
                (nt if r.is_trigger else np_).append(mnl)
            loc_fit = bug_rates(lt, lp)
            nloc_fit = bug_rates(nt, np_)
        w = _t9.wall_sec(d)
        camp_w = (state.get((project, bid)) or {}).get("wall_sec")
        if w is None and camp_w:
            try:
                w = float(camp_w)
            except ValueError:
                w = None
        if w is not None:
            walls.append(w)
        bug_rows.append(
            {
                "project": project,
                "bug_id": bid,
                "wall_sec": w,
                "has_nogain_trigger": len(nog_t) > 0,
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
                "has_locality": loc is not None,
                "excess_nogain_local": None if not loc_fit else loc_fit["excess"],
                "excess_nogain_nonlocal": None if not nloc_fit else nloc_fit["excess"],
            }
        )
        try:
            _, _, _, kills_nt = maps_with_kill_filter(d, trig, {"FAIL", "EXC"})
            rows_nt = build_events(project, bid, tests, triggers, covers, kills_nt, None)
            p_nt = bug_rates(*_t9.stratum_matchables(rows_nt, False))
            if p_nt:
                no_time_excess.append(p_nt["excess"])
            _, _, _, kills_f = maps_with_kill_filter(d, trig, {"FAIL"})
            rows_f = build_events(project, bid, tests, triggers, covers, kills_f, None)
            p_f = bug_rates(*_t9.stratum_matchables(rows_f, False))
            if p_f:
                fail_only_excess.append(p_f["excess"])
        except Exception:
            pass

    prim = [b for b in bug_rows if b["included_primary"]]
    primary_s = summarize_excess([b["excess_nogain"] for b in prim], BOOT_SEED)
    r_t = sum(b["r_trigger_nogain"] for b in prim) / len(prim) if prim else None
    r_p = sum(b["r_placebo_nogain"] for b in prim) / len(prim) if prim else None
    ratio, af = rr_af(r_t or 0, r_p or 0) if prim else (None, None)
    gain_bugs = [b for b in bug_rows if b["excess_gain"] is not None]
    gain_s = summarize_excess([b["excess_gain"] for b in gain_bugs], BOOT_SEED + 1)
    loc_bugs = [b for b in prim if b["excess_nogain_local"] is not None]
    nloc_bugs = [b for b in prim if b["excess_nogain_nonlocal"] is not None]
    loc_s = summarize_excess([b["excess_nogain_local"] for b in loc_bugs], BOOT_SEED + 2)
    nloc_s = summarize_excess([b["excess_nogain_nonlocal"] for b in nloc_bugs], BOOT_SEED + 3)
    kr_nt = summarize_excess(no_time_excess, BOOT_SEED + 4)
    kr_f = summarize_excess(fail_only_excess, BOOT_SEED + 5)

    status_counts = Counter()
    by_proj = defaultdict(lambda: Counter())
    for rec in man:
        st = (state.get((rec["project"], rec["bug_id"])) or {}).get("status") or rec["terminal_status"]
        status_counts[st] += 1
        by_proj[rec["project"]][st] += 1
        by_proj[rec["project"]]["active"] += 1

    attempted = sum(status_counts[k] for k in status_counts if k != "PENDING")
    valid = status_counts.get("COMPLETE_VALID", 0)
    valid_scientific = len(bug_rows)
    parser_fail = collisions_test
    g4 = [b for b in bug_rows if b["has_nogain_trigger"]]
    unmatched = len(g4) - len(prim)
    common_support = "ADEQUATE" if g4 and (len(prim) / len(g4) >= 0.8) else "INADEQUATE"

    loc_cov = (n_mutants_labeled / n_mutants_total) if n_mutants_total else 0.0
    n_trig_obs = sum(b["n_nogain_trigger"] for b in bug_rows)
    rq3_cov = 0.0
    rq3_gate = "FAIL"
    rq3_status = "SUPPLEMENTARY"

    half = primary_s["halfwidth"] if primary_s else None
    prec = "PASS" if (half is not None and half <= PRECISION_TARGET) else "FAIL"

    # missingness bounds: assign missing eligible bugs excess 0 or 1
    n_eligible_attempted_invalid = attempted - valid_scientific
    bounds = None
    if primary_s and n_eligible_attempted_invalid > 0:
        n = len(prim) + n_eligible_attempted_invalid
        s = primary_s["mean"] * len(prim)
        lo_b = s / n
        hi_b = (s + n_eligible_attempted_invalid) / n
        bounds = {
            "label": "BOUNDS / SENSITIVITY",
            "missing_attempted_invalid": n_eligible_attempted_invalid,
            "if_missing_excess_0": lo_b,
            "if_missing_excess_1": hi_b,
            "note": "Not an estimate. Extreme assignment of unobserved excess.",
        }

    summary = {
        "lock_git": LOCK_GIT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap": {"method": "percentile", "B": N_BOOT, "seed": BOOT_SEED, "unit": "bug"},
        "n_active": len(man),
        "n_attempted": attempted,
        "n_valid_maps_on_disk": valid,
        "n_valid": valid_scientific,
        "n_parser_excluded_from_canonical": parser_fail,
        "completion_rate": (valid_scientific / attempted) if attempted else None,
        "timeouts": status_counts.get("TIMEOUT", 0),
        "build_failures": status_counts.get("BUILD_FAILURE", 0),
        "mutation_failures": status_counts.get("MUTATION_FAILURE", 0),
        "parser_failures": parser_fail,
        "other_failures": status_counts.get("OTHER_FAILURE", 0),
        "canonical_test_id_collisions": collisions_test,
        "mutant_id_collisions": collisions_mut,
        "n_nogain_trigger_bugs": len(g4),
        "n_primary_matched": len(prim),
        "unmatched_nogain_trigger_bugs": unmatched,
        "r_trigger": r_t,
        "r_placebo": r_p,
        "excess": None if not primary_s else primary_s["mean"],
        "ci95": None if not primary_s else primary_s["ci95"],
        "ci_halfwidth": half,
        "precision_target_0p070": prec,
        "risk_ratio": ratio,
        "attributable_fraction": af,
        "common_support": common_support,
        "gain": None
        if not gain_s
        else {
            "n": gain_s["n"],
            "excess": gain_s["mean"],
            "ci95": gain_s["ci95"],
            "r_trigger": sum(b["r_trigger_gain"] for b in gain_bugs) / len(gain_bugs),
            "r_placebo": sum(b["r_placebo_gain"] for b in gain_bugs) / len(gain_bugs),
        },
        "locality_mapping_coverage": loc_cov,
        "rq2_local": None if not loc_s else {"n": loc_s["n"], "excess": loc_s["mean"], "ci95": loc_s["ci95"]},
        "rq2_nonlocal": None
        if not nloc_s
        else {"n": nloc_s["n"], "excess": nloc_s["mean"], "ci95": nloc_s["ci95"]},
        "rq3_provenance_coverage": rq3_cov,
        "rq3_support_gate": rq3_gate,
        "rq3_status": rq3_status,
        "recency": "NOT_ESTIMABLE",
        "kill_reason_no_time": None
        if not kr_nt
        else {"n": kr_nt["n"], "excess": kr_nt["mean"], "ci95": kr_nt["ci95"]},
        "kill_reason_fail_only": None
        if not kr_f
        else {"n": kr_f["n"], "excess": kr_f["mean"], "ci95": kr_f["ci95"]},
        "wall_median_sec": percentile(walls, 0.5),
        "wall_p75_sec": percentile(walls, 0.75),
        "wall_p90_sec": percentile(walls, 0.90),
        "cpu_hours": (sum(walls) / 3600.0) if walls else None,
        "missingness_bounds": bounds,
        "projects": sorted({r["project"] for r in man}),
        "status_counts": dict(status_counts),
    }

    (out / "primary_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "precision.json").write_text(
        json.dumps(
            {
                "target": PRECISION_TARGET,
                "halfwidth": half,
                "result": prec,
            },
            indent=2,
        )
        + "\n"
    )
    if primary_s:
        (out / "bootstrap_distribution.csv").write_text(
            "mean_excess\n" + "\n".join("%.10f" % x for x in primary_s["dist"]) + "\n"
        )
    with (out / "bug_level_results.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(bug_rows[0].keys()) if bug_rows else ["project"])
        w.writeheader()
        w.writerows(bug_rows)
    try:
        import pandas as pd

        pd.DataFrame(bug_rows).to_parquet(out / "bug_level_results.parquet", index=False)
    except Exception as exc:  # noqa: BLE001
        (out / "parquet_skip.txt").write_text(str(exc) + "\n")

    with (out / "sample_flow.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "project",
                "active",
                "pre_outcome_eligible",
                "previously_completed",
                "new_attempted",
                "valid_matrices",
                "timeouts",
                "build_failures",
                "mutation_failures",
                "other_failures",
                "primary_event_eligible",
                "nogain_trigger_support",
                "matched_control_support",
                "locality_support",
                "provenance_support",
            ]
        )
        prev_valid = {
            (r["project"], r["bug_id"])
            for r in man
            if r["already_attempted"] == "YES" and r["existing_valid_matrix"] == "YES"
        }
        for proj in sorted(by_proj):
            c = by_proj[proj]
            valid_p = c.get("COMPLETE_VALID", 0)
            prev = sum(1 for p, b in prev_valid if p == proj)
            new_att = sum(
                1
                for r in man
                if r["project"] == proj and r["needs_execution"] == "YES"
            )
            # new attempted among those: status not pending
            new_done = sum(
                1
                for r in man
                if r["project"] == proj
                and r["needs_execution"] == "YES"
                and ((state.get((r["project"], r["bug_id"])) or {}).get("status") not in ("PENDING", "RUNNING", None, ""))
            )
            elig = sum(1 for b in prim if b["project"] == proj)
            g4p = sum(1 for b in g4 if b["project"] == proj)
            locp = sum(1 for b in loc_bugs if b["project"] == proj)
            w.writerow(
                [
                    proj,
                    c["active"],
                    c["active"],
                    prev,
                    new_done,
                    valid_p,
                    c.get("TIMEOUT", 0),
                    c.get("BUILD_FAILURE", 0),
                    c.get("MUTATION_FAILURE", 0),
                    c.get("OTHER_FAILURE", 0),
                    elig,
                    g4p,
                    elig,
                    locp,
                    0,
                ]
            )

    with (out / "project_summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["project", "n_primary", "mean_excess", "mean_r_trigger", "mean_r_placebo"],
        )
        w.writeheader()
        for proj in sorted({b["project"] for b in prim}):
            pb = [b for b in prim if b["project"] == proj]
            w.writerow(
                {
                    "project": proj,
                    "n_primary": len(pb),
                    "mean_excess": sum(b["excess_nogain"] for b in pb) / len(pb),
                    "mean_r_trigger": sum(b["r_trigger_nogain"] for b in pb) / len(pb),
                    "mean_r_placebo": sum(b["r_placebo_nogain"] for b in pb) / len(pb),
                }
            )

    with (out / "locality_results.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["contrast", "n", "excess", "ci_lo", "ci_hi"])
        if loc_s:
            w.writerow(["PATCH_LINE_UNION_PATCH_METHOD", loc_s["n"], loc_s["mean"], loc_s["ci95"][0], loc_s["ci95"][1]])
        if nloc_s:
            w.writerow(["NONLOCAL", nloc_s["n"], nloc_s["mean"], nloc_s["ci95"][0], nloc_s["ci95"][1]])

    with (out / "provenance_results.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "n_trigger_obs", "note"])
        w.writerow(["UNKNOWN", n_trig_obs, "no validated D4J 3.0.1 chronology map"])

    with (out / "technical_failures.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["project", "bug_id", "status"])
        for rec in man:
            st = (state.get((rec["project"], rec["bug_id"])) or {}).get("status") or rec["terminal_status"]
            if st not in ("COMPLETE_VALID", "PENDING", "RUNNING"):
                w.writerow([rec["project"], rec["bug_id"], st])

    with (out / "compute_cost.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["project", "bug_id", "wall_sec"])
        w.writeheader()
        for b in bug_rows:
            w.writerow({"project": b["project"], "bug_id": b["bug_id"], "wall_sec": b["wall_sec"]})

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4))
        labels = sorted(status_counts)
        ax.bar(labels, [status_counts[k] for k in labels])
        ax.set_ylabel("Bugs")
        ax.set_title("FULL-STUDY CANDIDATE — sample flow statuses")
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()
        fig.savefig(figdir / "fig1_sample_flow.png", dpi=120)
        plt.close()

        if prim:
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.scatter(
                [b["r_placebo_nogain"] for b in prim],
                [b["r_trigger_nogain"] for b in prim],
                alpha=0.6,
            )
            ax.plot([0, 1], [0, 1], "--", color="gray")
            ax.set_xlabel("Matched non-trigger event rate (NO_GAIN)")
            ax.set_ylabel("Trigger event rate (NO_GAIN)")
            ax.set_title("FULL-STUDY CANDIDATE — primary paired rates")
            fig.tight_layout()
            fig.savefig(figdir / "fig2_nogain_paired_rates.png", dpi=120)
            plt.close()

        if primary_s and gain_s:
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.bar(["NO_GAIN (primary)", "COVERAGE_GAIN (secondary)"], [primary_s["mean"], gain_s["mean"]])
            ax.axhline(0, color="gray")
            ax.set_ylabel("Mean excess coupling")
            ax.set_title("FULL-STUDY CANDIDATE — strata")
            fig.tight_layout()
            fig.savefig(figdir / "fig3_strata_excess.png", dpi=120)
            plt.close()

        if loc_s and nloc_s:
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.bar(["Local unique-kill", "Non-local unique-kill"], [loc_s["mean"], nloc_s["mean"]])
            ax.axhline(0, color="gray")
            ax.set_ylabel("Mean excess")
            ax.set_title("FULL-STUDY CANDIDATE — locality (mapped subset)")
            fig.tight_layout()
            fig.savefig(figdir / "fig4_locality.png", dpi=120)
            plt.close()

        if prim:
            fig, ax = plt.subplots(figsize=(8, 4))
            projs = sorted({b["project"] for b in prim})
            means = [
                sum(b["excess_nogain"] for b in prim if b["project"] == p)
                / max(1, sum(1 for b in prim if b["project"] == p))
                for p in projs
            ]
            ax.bar(projs, means)
            ax.axhline(0, color="gray")
            ax.set_ylabel("Mean NO_GAIN excess")
            ax.set_title("FULL-STUDY CANDIDATE — project heterogeneity")
            fig.autofmt_xdate(rotation=40)
            fig.tight_layout()
            fig.savefig(figdir / "fig5_project_excess.png", dpi=120)
            plt.close()
    except Exception as exc:  # noqa: BLE001
        (out / "figures_skip.txt").write_text(str(exc) + "\n")

    print(json.dumps({k: summary[k] for k in (
        "n_valid", "n_primary_matched", "excess", "ci95", "ci_halfwidth",
        "precision_target_0p070", "common_support", "timeouts", "mutation_failures",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
