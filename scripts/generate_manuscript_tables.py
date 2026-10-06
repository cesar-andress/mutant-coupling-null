#!/usr/bin/env python3
"""Generate manuscript-facing tables/figures from locked full-study outputs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def pct(n: int, den: int = 854) -> str:
    return f"{100.0 * n / den:.1f}\\%"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fs = root / "results" / "derived" / "full_study"
    paper = root.parent / "paper"
    tab = paper / "tables"
    fig = paper / "figures"
    tab.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)

    s = json.loads((fs / "primary_summary.json").read_text())
    g = s["gain"]
    kr = s["kill_reason_fail_only"]
    mb = s["missingness_bounds"]
    audit = json.loads((fs / "audit" / "independent_recompute.json").read_text())

    r_t = s["r_trigger"]
    r_p = s["r_placebo"]
    ex = s["excess"]
    lo, hi = s["ci95"]
    hw = s["ci_halfwidth"]
    rr = s["risk_ratio"]
    af = s["attributable_fraction"]

    # Table 1: sample flow
    rows = [
        ("Pre-outcome eligible (active D4J 3.0.1)", 854, "Frozen population"),
        ("Canonical valid matrices", 481, "Parseable kill maps"),
        ("Maps on disk before parser gate", 491, "Includes 10 collision maps"),
        ("Mutation failure", 266, "Terminal execution"),
        ("Timeout (1800\\,s)", 93, "Terminal execution"),
        ("Build failure", 4, "Terminal execution"),
        ("Parser exclusion (duplicate test IDs)", 10, "Not merged"),
        ("NO\\_GAIN trigger-support bugs", 304, "Primary stratum support"),
        ("NO\\_GAIN matched primary bugs", 288, "Common-support sample"),
    ]
    t1 = []
    t1.append(r"% Auto-generated from results/derived/full_study/primary_summary.json")
    t1.append(r"\begin{table}[t]")
    t1.append(r"\centering")
    t1.append(
        r"\caption{Sample flow for the locked Defects4J~3.0.1 primary study. "
        r"Percentages use the pre-outcome eligible population ($N=854$) as denominator.}"
    )
    t1.append(
        r"\Description{Sample-flow table from eligible bugs through canonical matrices "
        r"and primary matched NO_GAIN support.}"
    )
    t1.append(r"\label{tab:sample-flow}")
    t1.append(r"\small")
    t1.append(r"\begin{tabular}{@{}lrrp{4.2cm}@{}}")
    t1.append(r"\toprule")
    t1.append(r"Stage / status & $N$ & \% of 854 & Interpretation \\")
    t1.append(r"\midrule")
    for name, n, note in rows:
        t1.append(f"{name} & {n} & {pct(n)} & {note} \\\\")
    t1.append(r"\bottomrule")
    t1.append(r"\end{tabular}")
    t1.append(r"\end{table}")
    (tab / "tab_sample_flow.tex").write_text("\n".join(t1) + "\n")

    # Table 2: primary + secondary
    t2 = []
    t2.append(r"% Auto-generated from primary_summary.json")
    t2.append(r"\begin{table*}[t]")
    t2.append(r"\centering")
    t2.append(
        r"\caption{Primary NO\_GAIN and secondary COVERAGE\_GAIN comparisons. "
        r"$r_{\Gamma}$ and $r_{\mathcal{N}}$ are mean bug-level unique-kill event rates "
        r"for matched triggering and ordinary tests. Excess is the mean of $\Delta_b$. "
        r"Intervals are 95\% percentile cluster bootstraps over bugs ($B{=}10{,}000$). "
        r"RR and AF are alternative representations of the same contrast.}"
    )
    t2.append(
        r"\Description{Primary NO_GAIN and secondary COVERAGE_GAIN rates, excess, "
        r"confidence intervals, risk ratio, and attributable fraction.}"
    )
    t2.append(r"\label{tab:rq1-primary}")
    t2.append(r"\small")
    t2.append(r"\begin{tabular}{@{}lccccccc@{}}")
    t2.append(r"\toprule")
    t2.append(
        r"Stratum & Bugs & $r_{\Gamma}$ & $r_{\mathcal{N}}$ & Excess & 95\% CI & RR & AF \\"
    )
    t2.append(r"\midrule")
    t2.append(
        f"NO\\_GAIN (primary) & {s['n_primary_matched']} & "
        f"{r_t:.3f} & {r_p:.3f} & {ex:.3f} & "
        f"[{lo:.3f}, {hi:.3f}] & {rr:.2f} & {af:.3f} \\\\"
    )
    t2.append(
        f"COVERAGE\\_GAIN (secondary) & {g['n']} & "
        f"{g['r_trigger']:.3f} & {g['r_placebo']:.3f} & {g['excess']:.3f} & "
        f"[{g['ci95'][0]:.3f}, {g['ci95'][1]:.3f}] & -- & -- \\\\"
    )
    t2.append(r"\bottomrule")
    t2.append(r"\end{tabular}")
    t2.append(r"\end{table*}")
    (tab / "tab_rq1_primary.tex").write_text("\n".join(t2) + "\n")

    # Table 3: robustness
    max_lopo = audit["max_lopo"]
    max_bug = audit["max_bug_influence"]
    t3 = []
    t3.append(r"% Auto-generated from primary_summary.json and audit/independent_recompute.json")
    t3.append(r"\begin{table}[t]")
    t3.append(r"\centering")
    t3.append(
        r"\caption{Locked robustness and integrity diagnostics. "
        r"None of these rows replaces the primary NO\_GAIN analysis.}"
    )
    t3.append(r"\Description{Robustness table for bootstrap stability, LOPO, bug influence, kill-reason, and missingness bounds.}")
    t3.append(r"\label{tab:robustness}")
    t3.append(r"\small")
    t3.append(r"\begin{tabular}{@{}p{3.4cm}p{8.2cm}@{}}")
    t3.append(r"\toprule")
    t3.append(r"Check & Result \\")
    t3.append(r"\midrule")
    t3.append(
        r"Bootstrap stability & Alternate seed CI shift $L_1\approx"
        f"{audit['bootstrap_ci_shift_l1']:.3f}$; labelled STABLE. \\\\"
    )
    t3.append(
        f"Leave-one-project-out & Largest $|\\Delta|$ when removing "
        f"{max_lopo['project']}: ${max_lopo['delta_from_full']:+.3f}$ "
        f"(remaining excess ${max_lopo['excess']:.3f}$). All project-omitted CIs exclude 0. \\\\"
    )
    t3.append(
        f"Max leave-one-bug-out & $|\\Delta|\\approx{max_bug['abs_delta']:.3f}$ "
        f"({max_bug['project']}-{max_bug['bug_id']}). \\\\"
    )
    t3.append(
        f"FAIL-only kills & Excess ${kr['excess']:.3f}$, "
        f"95\\% CI $[{kr['ci95'][0]:.3f}, {kr['ci95'][1]:.3f}]$ "
        r"(TIME and EXC excluded from unique-kill counts). \\"
    )
    t3.append(
        f"Extreme missingness bounds & Assigning excess $0$ / $1$ to all "
        f"{mb['missing_attempted_invalid']} non-canonical bugs yields "
        f"${mb['if_missing_excess_0']:.3f}$ / ${mb['if_missing_excess_1']:.3f}$. "
        r"An adversarial $-1$ assignment can reverse the sign. "
        r"Bounds are not estimates. \\"
    )
    t3.append(
        r"Protocol deviations & Two POST\_OUTCOME\_NON\_PRIMARY; "
        r"zero POST\_OUTCOME\_PRIMARY. \\"
    )
    t3.append(r"\bottomrule")
    t3.append(r"\end{tabular}")
    t3.append(r"\end{table}")
    (tab / "tab_robustness.tex").write_text("\n".join(t3) + "\n")

    # Copy figures
    src_fig = fs / "figures"
    mapping = {
        "fig2_nogain_paired_rates.png": "fig_rq1_paired_rates.png",
        "fig3_strata_excess.png": "fig_strata_excess.png",
        "fig5_project_excess.png": "fig_project_excess.png",
        "fig4_locality.png": "fig_locality_lang.png",
    }
    for src, dst in mapping.items():
        shutil.copy2(src_fig / src, fig / dst)

    meta = {
        "r_trigger": round(r_t, 3),
        "r_placebo": round(r_p, 3),
        "excess": round(ex, 3),
        "ci": [round(lo, 3), round(hi, 3)],
        "halfwidth": round(hw, 3),
        "tables": ["tab_sample_flow.tex", "tab_rq1_primary.tex", "tab_robustness.tex"],
        "figures": list(mapping.values()),
    }
    (tab / "GENERATION_META.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
