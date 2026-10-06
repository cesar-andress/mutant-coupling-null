#!/usr/bin/env python3
"""Generate manuscript-facing tables/figures from locked full-study + core completion."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def pct(n: int, den: int = 854) -> str:
    return f"{100.0 * n / den:.1f}\\%"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fs = root / "results" / "derived" / "full_study"
    cc = fs / "core_completion"
    paper = root.parent / "paper"
    tab = paper / "tables"
    fig = paper / "figures"
    tab.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)

    s = json.loads((fs / "primary_summary.json").read_text())
    c = json.loads((cc / "summary.json").read_text())
    g = s["gain"]
    kr = s["kill_reason_fail_only"]
    mb = s["missingness_bounds"]
    tip = c["tipping_point"]
    tax = c["mutation_failure_taxonomy"]

    r_t = s["r_trigger"]
    r_p = s["r_placebo"]
    ex = s["excess"]
    lo, hi = s["ci95"]
    hw = s["ci_halfwidth"]
    rr = s["risk_ratio"]
    af = s["attributable_fraction"]

    # Table 1: sample flow
    rows = [
        ("Pre-outcome target population (active D4J 3.0.1)", 854, "Benchmark population"),
        ("Matrix-available (canonical)", 481, "Collision-free kill maps"),
        ("Maps on disk before parser gate", 491, "Includes 10 collision maps"),
        ("Mutation failure", 266, "No canonical matrix"),
        ("Timeout (1800\\,s)", 93, "No canonical matrix"),
        ("Build failure", 4, "No canonical matrix"),
        ("Parser exclusion (duplicate test IDs)", 10, "Not merged"),
        ("NO\\_GAIN trigger-support", 304, "Primary stratum support"),
        ("NO\\_GAIN matched primary", 288, "Claim population"),
    ]
    t1 = [
        r"% Auto-generated from primary_summary.json",
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Sample flow for the Defects4J~3.0.1 study. "
        r"Percentages use the pre-outcome target population ($N=854$). "
        r"Matrix completion is not an eligibility criterion.}",
        r"\Description{Sample-flow table from target population through canonical matrices and primary matched NO_GAIN support.}",
        r"\label{tab:sample-flow}",
        r"\small",
        r"\begin{tabular}{@{}lrrp{4.0cm}@{}}",
        r"\toprule",
        r"Stage / status & $N$ & \% of 854 & Interpretation \\",
        r"\midrule",
    ]
    for name, n, note in rows:
        t1.append(f"{name} & {n} & {pct(n)} & {note} \\\\")
    t1 += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (tab / "tab_sample_flow.tex").write_text("\n".join(t1) + "\n")

    # Table 2: primary + secondary
    t2 = [
        r"% Auto-generated from primary_summary.json",
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Primary NO\_GAIN and secondary COVERAGE\_GAIN comparisons. "
        r"$r_{\Gamma}$ and $r_{\mathcal{N}}$ are mean bug-level unique-kill event rates "
        r"for matched triggering and ordinary reference tests. Excess is the mean of "
        r"$\Delta_b$. Intervals are 95\% percentile bootstraps over bugs ($B{=}10{,}000$). "
        r"RR and AF are computed from unrounded aggregate rates.}",
        r"\Description{Primary NO_GAIN and secondary COVERAGE_GAIN rates, excess, confidence intervals, risk ratio, and attributable fraction.}",
        r"\label{tab:rq1-primary}",
        r"\small",
        r"\begin{tabular}{@{}lccccccc@{}}",
        r"\toprule",
        r"Stratum & Bugs & $r_{\Gamma}$ & $r_{\mathcal{N}}$ & Excess & 95\% CI & RR & AF \\",
        r"\midrule",
        f"NO\\_GAIN (primary) & 288 & {r_t:.3f} & {r_p:.3f} & {ex:.3f} & "
        f"[{lo:.3f}, {hi:.3f}] & {rr:.2f} & {af:.3f} \\\\",
        f"COVERAGE\\_GAIN (secondary) & {g['n']} & "
        f"{g['r_trigger']:.3f} & {g['r_placebo']:.3f} & {g['excess']:.3f} & "
        f"[{g['ci95'][0]:.3f}, {g['ci95'][1]:.3f}] & -- & -- \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table*}",
    ]
    (tab / "tab_rq1_primary.tex").write_text("\n".join(t2) + "\n")

    # Table 3: robustness
    to = c["timeout_only"]
    sc = c["same_class_required"]
    st = c["single_trigger"]
    cl = c["project_clustered_bootstrap"]
    eq = c["equal_project_weight"]
    rw = c["project_mix_reweight"]
    hist = c["historical_fault_level"]
    mixed = c["model_check"]["mixed"]

    t3 = [
        r"% Auto-generated from core_completion/summary.json",
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Pre-specified checks and robustness diagnostics. "
        r"None replaces the locked primary NO\_GAIN bug-level bootstrap.}",
        r"\Description{Robustness table including mixed-model check, kill-reason, matching, clustering, and missingness tipping points.}",
        r"\label{tab:robustness}",
        r"\small",
        r"\begin{tabular}{@{}p{3.2cm}p{2.2cm}p{9.0cm}@{}}",
        r"\toprule",
        r"Analysis & Type & Result \\",
        r"\midrule",
        f"Mixed logistic (VB) & Pre-specified check & "
        f"Trigger OR $\\approx {mixed['trigger_or']:.1f}$ "
        f"(approx.\\ 95\\% CI $[{mixed['approx_ci95_or'][0]:.1f}, {mixed['approx_ci95_or'][1]:.1f}]$); "
        f"$n_{{\\mathrm{{rows}}}}={mixed['n_rows']}$, $n_{{\\mathrm{{bugs}}}}={mixed['n_bugs']}$. "
        r"Direction agrees with primary; not a replacement estimand. \\",
        f"Timeout-only kills excluded & Pre-specified sensitivity & "
        f"$n={to['n']}$; excess ${to['mean']:.3f}$, 95\\% CI $[{to['ci95'][0]:.3f}, {to['ci95'][1]:.3f}]$. \\\\",
        f"FAIL-only kills & Robustness & "
        f"$n={kr['n']}$; excess ${kr['excess']:.3f}$, 95\\% CI $[{kr['ci95'][0]:.3f}, {kr['ci95'][1]:.3f}]$. \\\\",
        f"Same-class matching required & Pre-specified variant & "
        f"$n={sc['n']}$; excess ${sc['mean']:.3f}$, 95\\% CI $[{sc['ci95'][0]:.3f}, {sc['ci95'][1]:.3f}]$ "
        f"(support loss vs 288). \\\\",
        f"Single-trigger bugs only & Post-hoc robustness & "
        f"$n={st['n']}$; excess ${st['mean']:.3f}$, 95\\% CI $[{st['ci95'][0]:.3f}, {st['ci95'][1]:.3f}]$. \\\\",
        f"Project-clustered bootstrap & Robustness CI & "
        f"Point ${cl['point_bug_weighted']:.3f}$; 95\\% CI $[{cl['ci95'][0]:.3f}, {cl['ci95'][1]:.3f}]$ "
        f"($B={cl['B']}$, {cl['n_projects']} projects). \\\\",
        f"Equal-project-weight mean & Robustness & "
        f"${eq['mean']:.3f}$, 95\\% CI $[{eq['ci95'][0]:.3f}, {eq['ci95'][1]:.3f}]$. \\\\",
        (
            "Project-mix reweight & Robustness & NOT\\_ESTIMABLE. \\\\"
            if rw["status"] != "COMPLETE"
            else f"Project-mix reweight & Robustness & ${rw['estimate']:.3f}$. \\\\"
        ),
        r"Leave-one-project-out & Robustness & "
        r"Largest shift $+0.041$ (omit Math); all omitted CIs exclude 0. \\",
        r"Max leave-one-bug-out & Robustness & $|\Delta|\approx 0.005$ (Lang-40). \\",
        f"Missingness tipping point & Diagnostic & "
        f"Conv.\\ A: $e={tip['convention_A_required_mean_excess']:.3f}$; "
        f"Conv.\\ B ($n_u={tip['convention_B_projected_primary_missing_n']}$): "
        f"$e={tip['convention_B_required_mean_excess']:.3f}$. Not estimates. \\\\",
        f"Fault-level reconstruction & Pipeline context & "
        f"{hist['n_coupled']}/{hist['n_evaluable']} ({hist['pct_coupled']:.1f}\\%) coupled; "
        r"not comparable as an excess estimand. \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table*}",
    ]
    (tab / "tab_robustness.tex").write_text("\n".join(t3) + "\n")

    # Table 4: failure taxonomy compact
    counts = tax["counts"]
    t4 = [
        r"% Auto-generated mutation-failure taxonomy",
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Technical taxonomy of 266 mutation failures from campaign logs. "
        r"All occurred before a usable unique-kill outcome existed.}",
        r"\Description{Mutation failure categories and counts.}",
        r"\label{tab:failure-taxonomy}",
        r"\small",
        r"\begin{tabular}{@{}lrr@{}}",
        r"\toprule",
        r"Category & $N$ & \% of 266 \\",
        r"\midrule",
    ]
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        t4.append(f"{cat.replace('_', '\\_')} & {n} & {100.0*n/266:.1f}\\% \\\\")
    t4 += [
        f"UNKNOWN & {tax['unknown']} & {100.0*tax['unknown']/266:.1f}\\% \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    (tab / "tab_failure_taxonomy.tex").write_text("\n".join(t4) + "\n")

    # Copy figures
    copies = [
        (fs / "figures" / "fig_rq1_paired_rates_jitter.png", fig / "fig_rq1_paired_rates.png"),
        (fs / "figures" / "fig_project_forest.png", fig / "fig_project_forest.png"),
        (cc / "figures" / "fig_rq1_paired_rates_jitter.png", fig / "fig_rq1_paired_rates.png"),
        (cc / "figures" / "fig_project_forest.png", fig / "fig_project_forest.png"),
    ]
    for src, dst in copies:
        if src.is_file():
            shutil.copy2(src, dst)

    meta = {
        "r_trigger": round(r_t, 3),
        "r_placebo": round(r_p, 3),
        "excess": round(ex, 3),
        "ci": [round(lo, 3), round(hi, 3)],
        "halfwidth": round(hw, 3),
        "core_completion_lock": c["lock_id"],
        "tables": [
            "tab_sample_flow.tex",
            "tab_rq1_primary.tex",
            "tab_robustness.tex",
            "tab_failure_taxonomy.tex",
        ],
        "figures": ["fig_rq1_paired_rates.png", "fig_project_forest.png"],
    }
    (tab / "GENERATION_META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("Wrote manuscript tables/figures into", paper)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
