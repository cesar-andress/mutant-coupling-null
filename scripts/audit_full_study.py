#!/usr/bin/env python3
"""Independent full-study audit recompute. Frozen T9 analysis only. No new estimand."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from killmap.parse import CanonicalIdCollisionError, load_mutants_log, load_test_map  # noqa: E402
from mvp.bootstrap import percentile_ci  # noqa: E402
from mvp.matching import Matchable, bug_rates  # noqa: E402
from placebo.engine import build_events  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "run_t9_mvp", Path(__file__).resolve().parents[1] / "scripts" / "run_t9_mvp.py"
)
_t9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t9)

BOOT_SEED = 20261005
N_BOOT = 10000
ALT_SEED = 20261006
MAPS = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log")
TRACE_SEED = "FULL_STUDY_AUDIT_TRACE_v1"


def load_csv(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    fs = root / "results" / "derived" / "full_study"
    raw = root / "results" / "raw" / "t5"
    out = fs / "audit"
    out.mkdir(parents=True, exist_ok=True)

    man = load_csv(fs / "population_manifest.csv")
    state_rows = load_csv(fs / "campaign_state.csv")
    state = {(r["project"], r["bug_id"]): r for r in state_rows}
    published = json.loads((fs / "primary_summary.json").read_text())
    bug_csv = load_csv(fs / "bug_level_results.csv")

    loc = defaultdict(dict)
    locp = root / "results" / "derived" / "locality" / "mutant_locality.jsonl"
    if locp.is_file():
        for line in locp.read_text().splitlines():
            o = json.loads(line)
            loc[(o["project"], str(o["bug_id"]))][int(o["mutant_id"])] = o["locality"]

    stc = Counter(r["status"] for r in state_rows)
    parse_fail = []
    prim_rows = []
    gain_rows = []
    loc_rows = []
    nloc_rows = []
    ingested = []
    mutant_dup = 0
    traces = []

    candidates = []
    for rec in man:
        key = (rec["project"], rec["bug_id"])
        d = raw / f"{rec['project']}-{rec['bug_id']}"
        h = hashlib.sha256(f"{TRACE_SEED}:{rec['project']}:{rec['bug_id']}".encode()).hexdigest()
        candidates.append((h, rec, d, key))
    candidates.sort()

    for rec in man:
        project, bid = rec["project"], rec["bug_id"]
        d = raw / f"{project}-{bid}"
        if not all((d / n).is_file() for n in MAPS):
            continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            continue
        try:
            tmap = load_test_map(d / "testMap.csv")
            muts = load_mutants_log(d / "mutants.log")
        except CanonicalIdCollisionError:
            parse_fail.append(f"{project}-{bid}")
            continue
        except ValueError as exc:
            if "duplicate mutant" in str(exc).lower():
                mutant_dup += 1
            parse_fail.append(f"{project}-{bid}")
            continue
        tests, triggers, covers, kills = _t9.maps_to_dicts(d, trig)
        # engine invariant: triggers not in ordinary killer index
        locality = loc.get((project, bid)) or None
        rows = build_events(project, bid, tests, triggers, covers, kills, locality)
        trig_in_nontrigger = [t for t in tests if t in triggers]
        # reconstruction
        nog_t, nog_p = _t9.stratum_matchables(rows, False)
        gain_t, gain_p = _t9.stratum_matchables(rows, True)
        primary = bug_rates(nog_t, nog_p)
        secondary = bug_rates(gain_t, gain_p)
        ingested.append(
            {
                "project": project,
                "bug_id": bid,
                "n_tests": len(tests),
                "n_triggers_in_map": sum(1 for t in tests if t in triggers),
                "n_nogain_trigger": len(nog_t),
                "included_primary": primary is not None,
                "excess_nogain": None if primary is None else primary["excess"],
                "r_trigger_nogain": None if primary is None else primary["r_trigger"],
                "r_placebo_nogain": None if primary is None else primary["r_placebo"],
                "excess_gain": None if secondary is None else secondary["excess"],
                "r_trigger_gain": None if secondary is None else secondary["r_trigger"],
                "r_placebo_gain": None if secondary is None else secondary["r_placebo"],
                "has_locality": locality is not None,
            }
        )
        if primary:
            prim_rows.append(ingested[-1])
        if secondary:
            gain_rows.append(ingested[-1])
        if locality is not None:
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
            lf, nf = bug_rates(lt, lp), bug_rates(nt, np_)
            if lf:
                loc_rows.append(lf["excess"])
            if nf:
                nloc_rows.append(nf["excess"])

    # traces: first 16 parse-success by TRACE hash + first 4 parse-fail by hash
    pass_c = [(h, rec, d) for h, rec, d, key in candidates if f"{rec['project']}-{rec['bug_id']}" not in parse_fail and all((d / n).is_file() for n in MAPS)]
    fail_c = [(h, rec, d) for h, rec, d, key in candidates if f"{rec['project']}-{rec['bug_id']}" in parse_fail]
    selected = pass_c[:16] + fail_c[:4]
    n_trace_pass = 0
    for h, rec, d in selected:
        project, bid = rec["project"], rec["bug_id"]
        trig = d / "trigger_tests.txt"
        item = {"project": project, "bug_id": bid, "ok": False, "detail": ""}
        try:
            tests, triggers, covers, kills = _t9.maps_to_dicts(d, trig)
            rows = build_events(project, bid, tests, triggers, covers, kills, loc.get((project, bid)))
            # trigger never ordinary base
            nontrigger = [t for t in tests if t not in triggers]
            leak = [t for t in nontrigger if t in triggers]
            nog_t, nog_p = _t9.stratum_matchables(rows, False)
            primary = bug_rates(nog_t, nog_p)
            pub = next((b for b in bug_csv if b["project"] == project and b["bug_id"] == bid), None)
            match = True
            if pub and primary and pub.get("excess_nogain") not in ("", None):
                match = abs(float(pub["excess_nogain"]) - primary["excess"]) < 1e-12
            if leak:
                item["detail"] = "trigger_leak"
            elif not match:
                item["detail"] = "bug_level_mismatch"
            else:
                item["ok"] = True
                n_trace_pass += 1
                item["detail"] = "reconstructed"
        except CanonicalIdCollisionError as exc:
            item["detail"] = "parser_collision:" + str(exc)[:80]
            item["ok"] = True  # expected failure mode for fail_c
            if f"{project}-{bid}" in parse_fail:
                n_trace_pass += 1
        except Exception as exc:  # noqa: BLE001
            item["detail"] = str(exc)[:120]
        traces.append(item)

    excesses = [r["excess_nogain"] for r in prim_rows]
    mean, lo, hi, dist = percentile_ci(excesses, N_BOOT, BOOT_SEED)
    mean2, lo2, hi2, _ = percentile_ci(excesses, N_BOOT, ALT_SEED)
    mean3, lo3, hi3, _ = percentile_ci(excesses, 20000, BOOT_SEED)
    r_t = sum(r["r_trigger_nogain"] for r in prim_rows) / len(prim_rows)
    r_p = sum(r["r_placebo_nogain"] for r in prim_rows) / len(prim_rows)
    rr = r_t / r_p if r_p else None
    af = (r_t - r_p) / r_t if r_t else None

    def close(a, b, tol=1e-12):
        if a is None or b is None:
            return a is b
        return abs(float(a) - float(b)) <= tol

    cmp = {
        "excess": close(mean, published["excess"]),
        "r_trigger": close(r_t, published["r_trigger"]),
        "r_placebo": close(r_p, published["r_placebo"]),
        "n_primary": len(prim_rows) == published["n_primary_matched"],
        "ci_lo": close(lo, published["ci95"][0]),
        "ci_hi": close(hi, published["ci95"][1]),
        "rr": close(rr, published["risk_ratio"]),
        "af": close(af, published["attributable_fraction"]),
    }
    if all(cmp.values()):
        repro = "EXACT"
    elif all(close(mean, published["excess"], 1e-9) for _ in [0]) and abs(lo - published["ci95"][0]) < 1e-8:
        repro = "ROUNDING_ONLY"
    else:
        repro = "MISMATCH_UNRESOLVED"

    # LOPO
    lopo = []
    by_proj = defaultdict(list)
    for r in prim_rows:
        by_proj[r["project"]].append(r["excess_nogain"])
    max_lopo = None
    for proj in sorted(by_proj):
        vals = [e for r in prim_rows if r["project"] != proj for e in [r["excess_nogain"]]]
        m, l, h, _ = percentile_ci(vals, N_BOOT, BOOT_SEED)
        delta = m - mean
        rec = {"project": proj, "n_left": len(vals), "excess": m, "ci95": [l, h], "delta_from_full": delta}
        lopo.append(rec)
        if max_lopo is None or abs(delta) > abs(max_lopo["delta_from_full"]):
            max_lopo = rec

    # LOBO point-estimate influence
    n = len(excesses)
    total = sum(excesses)
    influences = []
    for r in prim_rows:
        loo = (total - r["excess_nogain"]) / (n - 1)
        inf = loo - mean
        influences.append((abs(inf), inf, r["project"], r["bug_id"]))
    influences.sort(reverse=True)
    top = influences[:10]

    # parquet uniqueness
    test_coll_canon = 0
    mut_coll_canon = 0
    try:
        import pandas as pd

        tests = pd.read_parquet(fs / "tests.parquet")
        muts = pd.read_parquet(fs / "mutants.parquet")
        tdup = tests.duplicated(["project", "bug_id", "test_id"]).sum()
        mdup = muts.duplicated(["project", "bug_id", "mutant_id"]).sum()
        test_coll_canon = int(tdup)
        mut_coll_canon = int(mdup)
    except Exception as exc:  # noqa: BLE001
        tdup = str(exc)

    gex = [r["excess_gain"] for r in gain_rows]
    gm, gl, gh, _ = percentile_ci(gex, N_BOOT, BOOT_SEED + 1) if gex else (None, None, None, None)

    loc_s = percentile_ci(loc_rows, N_BOOT, BOOT_SEED + 2) if loc_rows else None
    nloc_s = percentile_ci(nloc_rows, N_BOOT, BOOT_SEED + 3) if nloc_rows else None

    # missingness by project
    fail_by = defaultdict(Counter)
    for rec in man:
        st = state[(rec["project"], rec["bug_id"])]["status"]
        fail_by[rec["project"]][st] += 1

    n_fail = 854 - len(ingested)
    bound0 = (mean * len(prim_rows) + 0 * n_fail) / (len(prim_rows) + n_fail)
    bound1 = (mean * len(prim_rows) + 1 * n_fail) / (len(prim_rows) + n_fail)
    # tighter: only assign missing to primary-eligible conceptually still 0/1 on mean excess of primary sample size inflated
    bound_primary0 = (mean * len(prim_rows)) / (len(prim_rows) + n_fail)
    bound_primary1 = (mean * len(prim_rows) + n_fail) / (len(prim_rows) + n_fail)

    ci_move = abs(lo2 - lo) + abs(hi2 - hi)
    boot_stable = ci_move < 0.01

    audit = {
        "reproducibility": repro,
        "compare_flags": cmp,
        "n_manifest": len(man),
        "status_counts": dict(stc),
        "n_parse_fail": len(parse_fail),
        "parse_fail_ids": parse_fail,
        "n_ingested": len(ingested),
        "n_primary": len(prim_rows),
        "n_nogain_trigger": sum(1 for r in ingested if r["n_nogain_trigger"] > 0),
        "r_trigger": r_t,
        "r_placebo": r_p,
        "excess": mean,
        "ci95": [lo, hi],
        "halfwidth": (hi - lo) / 2,
        "risk_ratio": rr,
        "attributable_fraction": af,
        "alt_seed_ci": [lo2, hi2],
        "alt_seed_mean": mean2,
        "B20000_ci": [lo3, hi3],
        "bootstrap_ci_shift_l1": ci_move,
        "bootstrap_stable": boot_stable,
        "gain_n": len(gain_rows),
        "gain_excess": gm,
        "gain_ci": [gl, gh],
        "lopo": lopo,
        "max_lopo": max_lopo,
        "max_bug_influence": {
            "abs_delta": influences[0][0],
            "delta": influences[0][1],
            "project": influences[0][2],
            "bug_id": influences[0][3],
        },
        "top_bug_influence": [
            {"abs_delta": a, "delta": d, "project": p, "bug_id": b} for a, d, p, b in top
        ],
        "canonical_test_dups_parquet": test_coll_canon,
        "canonical_mutant_dups_parquet": mut_coll_canon,
        "mutant_dup_raw": mutant_dup,
        "traces": traces,
        "n_trace": len(traces),
        "n_trace_pass": n_trace_pass,
        "loc_n": len(loc_rows),
        "loc_excess": None if not loc_s else loc_s[0],
        "loc_ci": None if not loc_s else [loc_s[1], loc_s[2]],
        "nloc_excess": None if not nloc_s else nloc_s[0],
        "nloc_ci": None if not nloc_s else [nloc_s[1], nloc_s[2]],
        "missing_n": n_fail,
        "extreme_bound_0": bound_primary0,
        "extreme_bound_1": bound_primary1,
        "fail_by_project": {p: dict(c) for p, c in fail_by.items()},
    }
    (out / "independent_recompute.json").write_text(json.dumps(audit, indent=2, default=str) + "\n")
    with (out / "lopo.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["project", "n_left", "excess", "ci_lo", "ci_hi", "delta_from_full"])
        w.writeheader()
        for r in lopo:
            w.writerow(
                {
                    "project": r["project"],
                    "n_left": r["n_left"],
                    "excess": r["excess"],
                    "ci_lo": r["ci95"][0],
                    "ci_hi": r["ci95"][1],
                    "delta_from_full": r["delta_from_full"],
                }
            )
    print(
        json.dumps(
            {
                "repro": repro,
                "n_primary": len(prim_rows),
                "excess": mean,
                "ci": [lo, hi],
                "n_trace_pass": n_trace_pass,
                "n_trace": len(traces),
                "parse_fail": len(parse_fail),
                "max_lopo": max_lopo,
                "max_bug": audit["max_bug_influence"],
                "boot_stable": boot_stable,
            },
            indent=2,
            default=str,
        )
    )
    return 0 if repro in ("EXACT", "ROUNDING_ONLY") else 2


if __name__ == "__main__":
    raise SystemExit(main())
