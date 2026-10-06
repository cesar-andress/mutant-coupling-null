#!/usr/bin/env python3
"""TOSEM core completion: existing-data analyses only (lock TOSEM-CORE-COMPLETION-20261006-V1)."""

from __future__ import annotations

import csv
import json
import math
import random
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from killmap.parse import load_pairs, load_test_map, parse_test_name  # noqa: E402
from mvp.bootstrap import percentile_ci  # noqa: E402
from mvp.matching import Matchable, bug_rates, exposure_bin, match_placebos, test_class  # noqa: E402
from placebo.engine import build_events  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "run_t9_mvp", Path(__file__).resolve().parents[1] / "scripts" / "run_t9_mvp.py"
)
_t9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t9)  # type: ignore[union-attr]

LOCK_ID = "TOSEM-CORE-COMPLETION-20261006-V1"
PRIMARY_BOOT_SEED = 20261005
N_BOOT = 10000
CLUSTER_SEED = 20261009
EQ_PROJ_SEED = 20261009 + 1
FOREST_SEED = 20261009 + 2
SINGLE_TRIG_SEED = 20261005 + 20
TIMEOUT_ONLY_SEED = 20261005 + 4
SAME_CLASS_SEED = 20261005 + 21
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


def match_placebos_same_class_only(trigger: Matchable, placebos):
    tbin = exposure_bin(trigger.n_mutants_covered)
    tclass = test_class(trigger.test_id)
    return [
        p
        for p in placebos
        if (not p.is_trigger)
        and p.coverage_gain == trigger.coverage_gain
        and exposure_bin(p.n_mutants_covered) == tbin
        and test_class(p.test_id) == tclass
    ]


def bug_rates_same_class(triggers, placebos):
    matched_t = []
    pair_placebo_means = []
    used = set()
    for t in triggers:
        ms = match_placebos_same_class_only(t, placebos)
        if not ms:
            continue
        matched_t.append(t)
        pair_placebo_means.append(sum(p.event for p in ms) / len(ms))
        used.update(p.test_id for p in ms)
    if not matched_t:
        return None
    r_t = sum(t.event for t in matched_t) / len(matched_t)
    r_p = sum(pair_placebo_means) / len(pair_placebo_means)
    return {
        "n_trigger_matched": len(matched_t),
        "n_placebo_matched_unique": len(used),
        "r_trigger": r_t,
        "r_placebo": r_p,
        "excess": r_t - r_p,
    }


def summarize(values, seed):
    if not values:
        return None
    mean, lo, hi, _ = percentile_ci(values, N_BOOT, seed)
    return {"n": len(values), "mean": mean, "ci95": [lo, hi], "halfwidth": (hi - lo) / 2}


def two_stage_project_bootstrap(by_project: dict[str, list[float]], seed: int, b: int = N_BOOT):
    projects = sorted(by_project)
    if not projects:
        return None
    # point: bug-weighted mean (same as primary) for comparison; also report
    all_vals = [v for p in projects for v in by_project[p]]
    point = sum(all_vals) / len(all_vals)
    rng = random.Random(seed)
    dist = []
    for _ in range(b):
        drawn_projects = [projects[rng.randrange(len(projects))] for _ in range(len(projects))]
        sample = []
        for p in drawn_projects:
            vals = by_project[p]
            if not vals:
                continue
            sample.extend(vals[rng.randrange(len(vals))] for _ in range(len(vals)))
        if sample:
            dist.append(sum(sample) / len(sample))
    dist.sort()
    lo = dist[int(0.025 * b)]
    hi = dist[min(b - 1, int(0.975 * b))]
    return {
        "n_projects": len(projects),
        "n_bugs": len(all_vals),
        "point_bug_weighted": point,
        "ci95": [lo, hi],
        "B": b,
        "seed": seed,
        "method": "two_stage_project_then_bug",
    }


def classify_mutation_failure(d: Path, return_code: str) -> str:
    stdout = (d / "mutation.stdout").read_text(errors="replace") if (d / "mutation.stdout").is_file() else ""
    stderr = (d / "mutation.stderr").read_text(errors="replace") if (d / "mutation.stderr").is_file() else ""
    compile_out = (d / "compile.stdout").read_text(errors="replace") if (d / "compile.stdout").is_file() else ""
    compile_err = (d / "compile.stderr").read_text(errors="replace") if (d / "compile.stderr").is_file() else ""
    tests_out = (d / "tests.stdout").read_text(errors="replace") if (d / "tests.stdout").is_file() else ""
    text = "\n".join([stdout, stderr, compile_out, compile_err, tests_out]).lower()
    files = {p.name for p in d.iterdir()} if d.is_dir() else set()

    if "outofmemory" in text or "out of memory" in text:
        return "RESOURCE_EXHAUSTION_OOM"
    if "mutation.test" in text and "fail" in text:
        return "MUTATION_TEST_FAIL"
    if "cannot mutate project" in text:
        return "MAJOR_MUTATE_FAILURE"
    if "compilation failed" in text or "compile failed" in text:
        return "COMPILE_FAILURE_DURING_MUTATION"
    if (d / "compile.exit").is_file() and (d / "compile.exit").read_text().strip() not in ("0", ""):
        return "FIXED_REVISION_COMPILE_FAILURE"
    if (d / "tests.exit").is_file() and (d / "tests.exit").read_text().strip() not in ("0", ""):
        return "RELEVANT_TESTS_FAILURE"
    if "killmap" in text and ("missing" in text or "not found" in text):
        return "KILLMAP_EXPORT_FAILURE"
    if "killMap.csv" not in files and "mutants.log" not in files:
        return "NO_MUTATION_ARTIFACTS"
    if "killMap.csv" not in files:
        return "MISSING_KILLMAP"
    if return_code == "124":
        return "TIMEOUT_MISCLASSIFIED"
    return "UNKNOWN"


def tertile_labels(n: int):
    # indices 0..n-1 into low/mid/high with as-equal sizes
    cuts = [int(round(n / 3)), int(round(2 * n / 3))]
    labs = []
    for i in range(n):
        if i < cuts[0]:
            labs.append("T1_low")
        elif i < cuts[1]:
            labs.append("T2_mid")
        else:
            labs.append("T3_high")
    return labs


def fit_mixed_or_clogit(rows_ml):
    """rows_ml: list of dicts with bug, event, trigger, coverage_gain, exposure."""
    import statsmodels.api as sm
    from statsmodels.discrete.conditional_models import ConditionalLogit
    from statsmodels.regression.mixed_linear_model import MixedLM

    y = np.array([r["event"] for r in rows_ml], dtype=float)
    trigger = np.array([r["trigger"] for r in rows_ml], dtype=float)
    gain = np.array([r["coverage_gain"] for r in rows_ml], dtype=float)
    # exposure: use log1p covered mutants
    exposure = np.array([math.log1p(r["n_mutants_covered"]) for r in rows_ml], dtype=float)
    bugs = np.array([r["bug"] for r in rows_ml])
    X = np.column_stack([trigger, gain, exposure])
    # Try mixed logistic via Bernoulli GLMM approximation: MixedLM on [0,1] is wrong.
    # Use Bayesian-free: Binomial Bayes not available. Prefer ConditionalLogit.
    # Methods order: mixed-effects logistic first. statsmodels has BinomialBayesMixedGLM
    # but may be heavy. Try MixedLM on latent scale as NOT matching Methods.
    # Use statsmodels.genmod.bayes_mixed_glm.BinomialBayesMixedGLM if available.
    result = {
        "mixed_status": None,
        "fallback_status": None,
        "mixed": None,
        "conditional_logit": None,
    }
    try:
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

        # formula-like via arrays: exog, exog_vc
        # Random intercept by bug: need design
        bug_ids, bug_index = np.unique(bugs, return_inverse=True)
        # BinomialBayesMixedGLM.from_formula easier with pandas
        import pandas as pd

        df = pd.DataFrame(
            {
                "event": y.astype(int),
                "trigger": trigger,
                "gain": gain,
                "exposure": exposure,
                "bug": bugs,
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = BinomialBayesMixedGLM.from_formula(
                "event ~ trigger + gain + exposure",
                {"bug": "0 + C(bug)"},
                df,
            )
            fit = model.fit_vb()
        # extract trigger coefficient
        names = list(fit.model.exog_names)
        # fit.params / fit.fe_mean
        fe = np.asarray(fit.fe_mean)
        fe_sd = np.asarray(fit.fe_sd)
        idx = names.index("trigger")
        coef = float(fe[idx])
        se = float(fe_sd[idx])
        result["mixed_status"] = "CONVERGED_VB"
        result["mixed"] = {
            "method": "BinomialBayesMixedGLM_VB",
            "trigger_coef_log_odds": coef,
            "trigger_se": se,
            "trigger_or": math.exp(coef),
            "approx_ci95_or": [math.exp(coef - 1.96 * se), math.exp(coef + 1.96 * se)],
            "n_rows": int(len(df)),
            "n_bugs": int(df["bug"].nunique()),
            "note": "Variational Bayes mixed logistic; check only, not primary.",
        }
        return result
    except Exception as exc:  # noqa: BLE001
        result["mixed_status"] = f"FAILED:{type(exc).__name__}:{exc}"

    # Fallback: conditional logit stratified by bug
    try:
        import pandas as pd

        df = pd.DataFrame(
            {
                "event": y.astype(int),
                "trigger": trigger,
                "gain": gain,
                "exposure": exposure,
                "bug": bugs,
            }
        )
        # ConditionalLogit requires groups with variation in outcome
        endog = df["event"]
        exog = df[["trigger", "gain", "exposure"]]
        groups = df["bug"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clog = ConditionalLogit(endog, exog, groups=groups)
            cres = clog.fit(disp=False, maxiter=200)
        params = cres.params
        bse = cres.bse
        coef = float(params["trigger"])
        se = float(bse["trigger"])
        result["fallback_status"] = "CONVERGED"
        result["conditional_logit"] = {
            "method": "ConditionalLogit_stratified_by_bug",
            "trigger_coef_log_odds": coef,
            "trigger_se": se,
            "trigger_or": math.exp(coef),
            "ci95_or": [
                math.exp(coef - 1.96 * se),
                math.exp(coef + 1.96 * se),
            ],
            "n_rows": int(len(df)),
            "n_bugs": int(df["bug"].nunique()),
            "converged": bool(cres.mle_retvals.get("converged", True)),
        }
    except Exception as exc:  # noqa: BLE001
        result["fallback_status"] = f"FAILED:{type(exc).__name__}:{exc}"
    return result


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    fs = root / "results" / "derived" / "full_study"
    out = fs / "core_completion"
    figdir = out / "figures"
    out.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)

    primary = json.loads((fs / "primary_summary.json").read_text())
    primary_mean = float(primary["excess"])
    n_primary = int(primary["n_primary_matched"])
    n_canonical = int(primary["n_valid"])
    n_missing = 854 - n_canonical

    state = {}
    with (fs / "campaign_state.csv").open() as fh:
        for rec in csv.DictReader(fh):
            state[(rec["project"], rec["bug_id"])] = rec

    man = list(csv.DictReader((fs / "population_manifest.csv").open()))
    target_by_proj = Counter(r["project"] for r in man)

    # --- mutation failure taxonomy ---
    tax_rows = []
    tax_counts = Counter()
    tax_by_proj = defaultdict(Counter)
    for rec in man:
        st = (state.get((rec["project"], rec["bug_id"])) or {}).get("status") or rec["terminal_status"]
        if st != "MUTATION_FAILURE":
            continue
        d = raw / f"{rec['project']}-{rec['bug_id']}"
        rc = (state.get((rec["project"], rec["bug_id"])) or {}).get("return_code", "")
        cat = classify_mutation_failure(d, rc)
        tax_counts[cat] += 1
        tax_by_proj[rec["project"]][cat] += 1
        tax_rows.append(
            {
                "project": rec["project"],
                "bug_id": rec["bug_id"],
                "category": cat,
                "return_code": rc,
                "before_outcome": "YES",
            }
        )

    # --- scan canonical maps ---
    bug_level = []
    ml_rows = []
    u_trig = []
    u_ref = []
    hist_rows = []
    same_class_excess = []
    single_trig_excess = []
    timeout_only_excess = []
    fail_only_excess = []

    for rec in man:
        project, bid = rec["project"], rec["bug_id"]
        d = raw / f"{project}-{bid}"
        st = (state.get((project, bid)) or {}).get("status") or rec["terminal_status"]
        if not all((d / n).is_file() for n in MAPS):
            continue
        trig = d / "trigger_tests.txt"
        if not trig.is_file():
            continue
        try:
            tests, triggers, covers, kills = maps_with_kill_filter(d, trig, None)
        except Exception:
            continue

        rows = build_events(project, bid, tests, triggers, covers, kills, None)
        # historical fault-level
        coupled = any(r.is_trigger and r.event for r in rows)
        hist_rows.append(
            {
                "project": project,
                "bug_id": bid,
                "coupled": int(coupled),
                "n_tests": len(tests),
                "n_triggers_mapped": sum(1 for t in tests if t in triggers),
            }
        )

        nog_t, nog_p = _t9.stratum_matchables(rows, False)
        primary_fit = bug_rates(nog_t, nog_p)
        sc_fit = bug_rates_same_class(nog_t, nog_p)
        n_trig_mapped = sum(1 for t in tests if t in triggers)
        wall = _t9.wall_sec(d)
        camp_w = (state.get((project, bid)) or {}).get("wall_sec")
        if wall is None and camp_w:
            try:
                wall = float(camp_w)
            except ValueError:
                wall = None

        # |U| for matched NO_GAIN
        if primary_fit is not None:
            for t in nog_t:
                ms = match_placebos(t, nog_p)
                if not ms:
                    continue
                # find event row
                er = next(r for r in rows if r.test_id == t.test_id)
                u_trig.append(er.n_unique_kills)
                for p in ms:
                    pr = next(r for r in rows if r.test_id == p.test_id)
                    u_ref.append(pr.n_unique_kills)

        # mixed-model rows: all NO_GAIN + COVERAGE_GAIN tests (event-level)
        for r in rows:
            ml_rows.append(
                {
                    "bug": f"{project}-{bid}",
                    "event": int(r.event),
                    "trigger": int(r.is_trigger),
                    "coverage_gain": int(r.coverage_gain),
                    "n_mutants_covered": int(r.n_mutants_covered),
                }
            )

        bl = {
            "project": project,
            "bug_id": bid,
            "n_tests": len(tests),
            "n_triggers_mapped": n_trig_mapped,
            "wall_sec": wall,
            "included_primary": primary_fit is not None,
            "has_nogain_trigger": len(nog_t) > 0,
            "r_trigger": None if not primary_fit else primary_fit["r_trigger"],
            "r_placebo": None if not primary_fit else primary_fit["r_placebo"],
            "excess": None if not primary_fit else primary_fit["excess"],
            "same_class_excess": None if not sc_fit else sc_fit["excess"],
            "same_class_r_trigger": None if not sc_fit else sc_fit["r_trigger"],
            "same_class_r_placebo": None if not sc_fit else sc_fit["r_placebo"],
            "fault_level_coupled": int(coupled),
        }
        if sc_fit is not None:
            same_class_excess.append(sc_fit["excess"])
        if primary_fit is not None and n_trig_mapped == 1:
            single_trig_excess.append(primary_fit["excess"])
            bl["single_trigger_primary"] = True
        else:
            bl["single_trigger_primary"] = bool(primary_fit is not None and n_trig_mapped == 1)

        # kill-reason sensitivities
        try:
            _, _, _, kills_nt = maps_with_kill_filter(d, trig, {"FAIL", "EXC"})
            rows_nt = build_events(project, bid, tests, triggers, covers, kills_nt, None)
            p_nt = bug_rates(*_t9.stratum_matchables(rows_nt, False))
            if p_nt:
                timeout_only_excess.append(p_nt["excess"])
            _, _, _, kills_f = maps_with_kill_filter(d, trig, {"FAIL"})
            rows_f = build_events(project, bid, tests, triggers, covers, kills_f, None)
            p_f = bug_rates(*_t9.stratum_matchables(rows_f, False))
            if p_f:
                fail_only_excess.append(p_f["excess"])
        except Exception:
            pass

        bug_level.append(bl)

    prim = [b for b in bug_level if b["included_primary"]]
    assert len(prim) == n_primary, f"primary n mismatch {len(prim)} vs {n_primary}"

    # tipping points
    tip_a = -(n_primary * primary_mean) / n_missing
    n_u_b = int(round(n_missing * (n_primary / n_canonical)))
    tip_b = -(n_primary * primary_mean) / n_u_b if n_u_b else None

    # project clustered
    by_proj = defaultdict(list)
    for b in prim:
        by_proj[b["project"]].append(b["excess"])
    clustered = two_stage_project_bootstrap(by_proj, CLUSTER_SEED, N_BOOT)

    # equal project weight
    proj_means = {p: sum(vs) / len(vs) for p, vs in by_proj.items()}
    eq_mean = sum(proj_means.values()) / len(proj_means)
    rng = random.Random(EQ_PROJ_SEED)
    pnames = sorted(proj_means)
    eq_dist = []
    for _ in range(N_BOOT):
        draw = [proj_means[pnames[rng.randrange(len(pnames))]] for _ in range(len(pnames))]
        eq_dist.append(sum(draw) / len(draw))
    eq_dist.sort()
    eq_ci = [eq_dist[int(0.025 * N_BOOT)], eq_dist[min(N_BOOT - 1, int(0.975 * N_BOOT))]]

    # project-mix reweighting
    missing_projects = [p for p, n in target_by_proj.items() if n > 0 and len(by_proj.get(p, [])) == 0]
    if missing_projects:
        reweight = {
            "status": "NOT_ESTIMABLE",
            "reason": "target projects with zero primary matched support",
            "zero_support_projects": sorted(missing_projects),
        }
    else:
        wsum = 0.0
        wex = 0.0
        for b in prim:
            p = b["project"]
            w = target_by_proj[p] / len(by_proj[p])
            wsum += w
            wex += w * b["excess"]
        reweight = {
            "status": "COMPLETE",
            "estimate": wex / wsum,
            "formula": "w_p = N_target_p / N_matched_p; weighted mean of bug excess",
        }

    # tertiles
    def tertile_table(key):
        rows = [b for b in prim if b[key] is not None]
        rows.sort(key=lambda b: (b[key], b["project"], b["bug_id"]))
        labs = tertile_labels(len(rows))
        out_rows = []
        for lab in ("T1_low", "T2_mid", "T3_high"):
            g = [rows[i] for i, L in enumerate(labs) if L == lab]
            if not g:
                continue
            out_rows.append(
                {
                    "tertile": lab,
                    "n": len(g),
                    "r_trigger": sum(x["r_trigger"] for x in g) / len(g),
                    "r_placebo": sum(x["r_placebo"] for x in g) / len(g),
                    "excess": sum(x["excess"] for x in g) / len(g),
                    "min": min(x[key] for x in g),
                    "max": max(x[key] for x in g),
                }
            )
        return out_rows

    tert_suite = tertile_table("n_tests")
    tert_wall = tertile_table("wall_sec")

    # historical
    n_hist = len(hist_rows)
    n_coupled = sum(r["coupled"] for r in hist_rows)
    hist_pct = 100.0 * n_coupled / n_hist if n_hist else None
    hist_by_proj = {}
    for p in sorted({r["project"] for r in hist_rows}):
        g = [r for r in hist_rows if r["project"] == p]
        hist_by_proj[p] = {
            "n": len(g),
            "coupled": sum(r["coupled"] for r in g),
            "pct": 100.0 * sum(r["coupled"] for r in g) / len(g),
        }

    # |U| summaries
    def iqr_summary(xs):
        if not xs:
            return None
        a = sorted(xs)
        def q(p):
            return a[min(len(a) - 1, max(0, int(round(p * (len(a) - 1)))))]
        return {
            "n": len(a),
            "median": q(0.5),
            "q1": q(0.25),
            "q3": q(0.75),
            "mean": sum(a) / len(a),
        }

    # model check — restrict to rows in primary bugs for stability? Methods say
    # bug-by-test rows; use all matrix-available tests.
    model = fit_mixed_or_clogit(ml_rows)

    timeout_s = summarize(timeout_only_excess, TIMEOUT_ONLY_SEED)
    fail_s = summarize(fail_only_excess, PRIMARY_BOOT_SEED + 5)
    same_s = summarize(same_class_excess, SAME_CLASS_SEED)
    single_s = summarize(single_trig_excess, SINGLE_TRIG_SEED)

    # forest data
    forest = []
    for p in sorted(by_proj):
        vals = by_proj[p]
        mean = sum(vals) / len(vals)
        ci = None
        if len(vals) >= 8:
            m, lo, hi, _ = percentile_ci(vals, 2000, FOREST_SEED + sum(ord(c) for c in p))
            ci = [lo, hi]
        n_target = target_by_proj[p]
        n_canon = sum(1 for b in bug_level if b["project"] == p)
        forest.append(
            {
                "project": p,
                "n_matched": len(vals),
                "excess": mean,
                "ci95": ci,
                "n_target": n_target,
                "n_canonical": n_canon,
                "completion_rate": n_canon / n_target if n_target else None,
            }
        )

    # figures
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # forest
    fig, ax = plt.subplots(figsize=(7.2, 8.5))
    ys = list(range(len(forest)))
    xs = [r["excess"] for r in forest]
    ax.axvline(0.0, color="0.5", lw=0.8)
    ax.axvline(primary_mean, color="0.2", ls="--", lw=0.8, label=f"primary mean {primary_mean:.3f}")
    for y, r in zip(ys, forest):
        ax.plot(r["excess"], y, "o", color="C0", ms=5)
        if r["ci95"]:
            ax.plot(r["ci95"], [y, y], color="C0", lw=1.2)
        label = f"{r['project']} (n={r['n_matched']}, cmp={100*r['completion_rate']:.0f}%)"
        ax.text(-0.05, y, label, ha="right", va="center", fontsize=7, transform=ax.get_yaxis_transform())
    ax.set_yticks([])
    ax.set_xlabel("Mean bug-level excess (NO_GAIN matched)")
    ax.set_title("Project-level excess among primary matched bugs")
    ax.set_xlim(-0.2, 1.05)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    forest_path = figdir / "fig_project_forest.png"
    fig.savefig(forest_path, dpi=160)
    # also copy to paper-facing full_study figures
    fig.savefig(fs / "figures" / "fig_project_forest.png", dpi=160)
    plt.close(fig)

    # improved paired rates
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    rt = np.array([b["r_trigger"] for b in prim])
    rp = np.array([b["r_placebo"] for b in prim])
    rngj = np.random.default_rng(20261009)
    jx = rngj.normal(0, 0.015, size=len(rt))
    jy = rngj.normal(0, 0.015, size=len(rp))
    ax.scatter(np.clip(rp + jx, -0.02, 1.02), np.clip(rt + jy, -0.02, 1.02), s=12, alpha=0.35, edgecolors="none")
    ax.plot([0, 1], [0, 1], color="0.4", lw=0.8)
    ax.axhline(float(primary["r_trigger"]), color="C3", ls="--", lw=0.7, label="mean trigger")
    ax.axvline(float(primary["r_placebo"]), color="C1", ls="--", lw=0.7, label="mean ordinary")
    ax.set_xlabel("Matched ordinary reference rate")
    ax.set_ylabel("Trigger rate")
    ax.set_title(f"NO_GAIN paired rates (n={len(prim)}; jittered)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_aspect("equal")
    ax.legend(fontsize=7)
    fig.tight_layout()
    paired_path = figdir / "fig_rq1_paired_rates_jitter.png"
    fig.savefig(paired_path, dpi=160)
    fig.savefig(fs / "figures" / "fig_rq1_paired_rates_jitter.png", dpi=160)
    # also overwrite manuscript-facing primary figure name used by generator
    fig.savefig(fs / "figures" / "fig2_nogain_paired_rates.png", dpi=160)
    plt.close(fig)

    summary = {
        "lock_id": LOCK_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_unchanged": {
            "n": n_primary,
            "r_trigger": primary["r_trigger"],
            "r_placebo": primary["r_placebo"],
            "excess": primary["excess"],
            "ci95": primary["ci95"],
        },
        "model_check": model,
        "timeout_only": timeout_s,
        "fail_only": fail_s,
        "same_class_required": {
            **(same_s or {}),
            "n_trigger_support_bugs": sum(1 for b in bug_level if b["has_nogain_trigger"]),
            "n_matched": None if not same_s else same_s["n"],
            "support_note": "Requires same test class; no bin-wide fallback",
        },
        "single_trigger": {
            **(single_s or {}),
            "n_canonical_single_trigger": sum(1 for b in bug_level if b["n_triggers_mapped"] == 1),
            "n_primary_single_trigger": sum(1 for b in prim if b["n_triggers_mapped"] == 1),
        },
        "project_clustered_bootstrap": clustered,
        "equal_project_weight": {
            "mean": eq_mean,
            "ci95": eq_ci,
            "n_projects": len(proj_means),
            "project_means": proj_means,
            "B": N_BOOT,
            "seed": EQ_PROJ_SEED,
        },
        "mutation_failure_taxonomy": {
            "n": sum(tax_counts.values()),
            "counts": dict(tax_counts),
            "unknown": tax_counts.get("UNKNOWN", 0),
            "by_project_top": {
                p: dict(c) for p, c in sorted(tax_by_proj.items(), key=lambda kv: -sum(kv[1].values()))[:8]
            },
        },
        "tipping_point": {
            "primary_mean_unrounded": primary_mean,
            "n_primary": n_primary,
            "n_missing_canonical": n_missing,
            "convention_A_required_mean_excess": tip_a,
            "convention_B_projected_primary_missing_n": n_u_b,
            "convention_B_required_mean_excess": tip_b,
            "label": "TIPPING_POINT_ANALYSIS",
        },
        "tertiles_suite_size": tert_suite,
        "tertiles_runtime": tert_wall,
        "project_mix_reweight": reweight,
        "historical_fault_level": {
            "n_evaluable": n_hist,
            "n_coupled": n_coupled,
            "pct_coupled": hist_pct,
            "by_project": hist_by_proj,
            "comparison_wording": "may_reflect_differences",
        },
        "unique_kill_counts": {
            "trigger_matched_nogain": iqr_summary(u_trig),
            "ordinary_matched_references": iqr_summary(u_ref),
        },
        "figures": {
            "forest": str(forest_path.relative_to(root)),
            "paired_jitter": str(paired_path.relative_to(root)),
        },
    }

    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (out / "mutation_failure_taxonomy.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["project", "bug_id", "category", "return_code", "before_outcome"])
        w.writeheader()
        w.writerows(tax_rows)
    with (out / "historical_fault_level.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["project", "bug_id", "coupled", "n_tests", "n_triggers_mapped"])
        w.writeheader()
        w.writerows(hist_rows)
    with (out / "project_forest.csv").open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "project",
                "n_matched",
                "excess",
                "ci_lo",
                "ci_hi",
                "n_target",
                "n_canonical",
                "completion_rate",
            ],
        )
        w.writeheader()
        for r in forest:
            w.writerow(
                {
                    "project": r["project"],
                    "n_matched": r["n_matched"],
                    "excess": r["excess"],
                    "ci_lo": None if not r["ci95"] else r["ci95"][0],
                    "ci_hi": None if not r["ci95"] else r["ci95"][1],
                    "n_target": r["n_target"],
                    "n_canonical": r["n_canonical"],
                    "completion_rate": r["completion_rate"],
                }
            )
    with (out / "bug_level_completion.csv").open("w", newline="") as fh:
        fields = list(bug_level[0].keys())
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(bug_level)

    print(json.dumps({k: summary[k] for k in summary if k not in ("equal_project_weight",)}, indent=2)[:4000])
    print("equal_project_weight", summary["equal_project_weight"]["mean"], summary["equal_project_weight"]["ci95"])
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
