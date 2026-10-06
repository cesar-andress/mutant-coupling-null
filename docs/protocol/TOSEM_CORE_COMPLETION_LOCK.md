# TOSEM core completion lock

LOCKED_AT: 2026-10-06T16:05:00Z  
LOCK_ID: TOSEM-CORE-COMPLETION-20261006-V1  
AUTHOR: César Andrés (ORCID 0009-0001-8968-3404)  
STATUS: FROZEN before executing authorized existing-data analyses.

Parent evidence:
- Full-study protocol lock `FULL_STUDY_PROTOCOL_LOCK.md` (git `75ad2fa31`)
- Locked primary NO_GAIN result in `results/derived/full_study/primary_summary.json`
- Independent recompute EXACT
- Independent TOSEM adversarial review archived as
  `CLAUDE_TOSEM_ADVERSARIAL_REVIEW_2026-10-06.md`

## Hard constraints

1. **No new mutation acquisition.** No Major reruns, no PIT, no second
   benchmark, no buggy-version mutation, no replacement pipeline.
2. **Primary estimand unchanged.** Matching bins, NO_GAIN primacy, event
   definition, bug-level percentile bootstrap (B=10000, seed=20261005), and
   the locked scalars (n=288; rates 0.649/0.227; excess 0.423;
   CI [0.362, 0.481]) remain authoritative.
3. **No result from this lock may alter the locked primary definition.**
4. Analyses below are PRE-SPECIFIED CHECK, PRE-SPECIFIED SENSITIVITY,
   POST-HOC ROBUSTNESS, or EXISTING-DATA DIAGNOSTIC only.

## Population terminology (writing, not redefinition)

| Term | N | Meaning |
|---|---|---|
| Benchmark / pre-outcome target population | 854 | Active D4J 3.0.1 bugs meeting pre-outcome eligibility (matrix completion is **not** eligibility) |
| Matrix-available / canonical population | 481 | Collision-free parseable kill maps |
| Primary NO_GAIN trigger-support population | 304 | Canonical bugs with ≥1 NO_GAIN trigger observation |
| Primary matched population | 288 | Trigger-support bugs with ≥1 matched ordinary reference under locked matching |

## Authorized analyses

### A. Pre-specified model check (Methods § estimand / stats)

- Mixed-effects logistic regression on bug-by-test rows:
  - outcome: unique-kill event \(E\)
  - fixed: trigger status, coverage-gain stratum, mutation-exposure covariate
    (`n_mutants_covered` or locked exposure bin)
  - random: bug-level intercept
- Fallback if separation / singularity / non-convergence:
  **conditional logistic regression stratified by bug** (already specified in
  Methods).
- Label: `PRE_SPECIFIED_CHECK`. Does not replace primary bootstrap.

### B. Timeout-only exclusion (pre-specified kill-reason sensitivity)

- Recompute unique kills counting only Major statuses that are **not** `TIME`
  (i.e. allow `FAIL` and `EXC`; exclude timeout kills).
- This is distinct from FAIL-only (`FAIL` alone).
- Seed for CI: `20261005 + 4` (matches existing full-study analysis).
- Label: `PRE_SPECIFIED_SENSITIVITY`.

### C. Same-test-class matching variant

- Primary matching already prefers same class when support exists.
- Variant: **require** same test class (no fallback to all placebos in the
  exposure bin).
- Report support loss. Label: `PRE_SPECIFIED_VARIANT` (Methods “where support
  allows” completeness).

### D. Single-trigger-bug sensitivity

- Restrict to bugs with exactly one mapped triggering test in the matrix.
- Same locked event, stratum, matching, bootstrap (seed `20261005 + 20`).
- Label: `POST_HOC_ROBUSTNESS` (co-trigger asymmetry).

### E. Project-clustered / two-stage bootstrap

- Resample **projects** with replacement among projects that contribute at
  least one primary matched bug; within each drawn project, resample its
  primary matched bugs with replacement.
- If a resampled project has zero bugs drawn, skip contribution for that
  project draw (standard two-stage).
- Mean excess over the resulting bug multiset.
- B = 10_000, seed = `20261009` (frozen here before observing output).
- Label: `PROJECT_CLUSTERED_ROBUSTNESS_CI`. Not primary.

### F. Equal-project-weight mean

- For each project with ≥1 primary matched bug, compute mean bug-level excess.
- Report unweighted mean of those project means.
- Optional bootstrap: resample projects with replacement (seed `20261009+1`,
  B=10_000) of the project means.
- Label: `EQUAL_PROJECT_WEIGHT_ROBUSTNESS`.

### G. Mutation-failure taxonomy

- Classify the 266 `MUTATION_FAILURE` rows using campaign/mutation logs only.
- Finest reliable categories; retain `UNKNOWN` when unsupported.
- Label: `EXISTING_DATA_DIAGNOSTIC`.

### H. Missingness tipping-point analysis

- Convention A: treat all 373 non-canonical target-population bugs as if they
  were primary-eligible; solve for mean unobserved excess \(e\) s.t.
  \((288\cdot 0.4227434637581891 + 373\cdot e)/(288+373)=0\).
- Convention B: project primary-support fraction \(288/481\) onto the 373
  missing bugs → \(n_u=\mathrm{round}(373\cdot 288/481)\); solve
  \((288\cdot \bar\Delta + n_u\cdot e)/(288+n_u)=0\).
- Use exact unrounded primary mean from `primary_summary.json`.
- Label: `TIPPING_POINT_ANALYSIS` (not an estimate).

### I. Completed-bug suite-size / runtime tertiles

- Pre-freeze variables (completed / matrix-available bugs only):
  1. suite size = number of tests in the kill map
  2. runtime = recorded wall seconds
- Among primary matched bugs, tertile by each variable (ties broken by
  project, bug_id).
- Report N, rates, excess per tertile. No interaction claims.
- Label: `MISSINGNESS_DIAGNOSTIC`.

### J. Project-mix reweighting

- Weight each primary matched bug by
  \(w_p = N^{\mathrm{target}}_p / N^{\mathrm{matched}}_p\) for its project \(p\),
  where \(N^{\mathrm{target}}_p\) is the 854-population project count and
  \(N^{\mathrm{matched}}_p\) is the primary-matched count.
- Estimator: weighted mean of bug-level excess.
- If any target project has matched count 0 while target count > 0:
  report `NOT_ESTIMABLE` rather than inventing weights.
- Label: `PROJECT_MIX_REWEIGHT_ROBUSTNESS`.

### K. Full 481-bug fault-level historical reconstruction

- For every canonical bug: fault coupled iff ≥1 trigger uniquely kills ≥1
  mutant relative to the ordinary base (existing engine / anchor predicate).
- Report evaluable N, coupled count, percentage; wording **may reflect**
  differences vs historical ~73%, never causal attribution.
- Label: `PIPELINE_CONTEXT`.

### L. Unique-kill count descriptor \(|U|\)

- Report distributions of `n_unique_kills` for matched NO_GAIN triggering
  tests and matched ordinary reference tests (median, IQR).
- Label: `SECONDARY_DESCRIPTOR`.

### M. Project forest plot + improved paired figure

- Forest: per-project mean excess among primary matched bugs; annotate n and
  completion rate; CI only when project n ≥ 8 (percentile bootstrap B=2000,
  seed `20261009+2`).
- Paired figure: reduce overplotting (jitter / marginals) without changing data.

## Explicitly NOT authorized

PIT; second benchmark; buggy-version mutation; locality remapping expansion;
provenance reconstruction; recency invention; alternative primary matching;
coverage redefinition; SOTA reopen; Zenodo/DOI/release.

## Output paths

Public derived:

`results/derived/full_study/core_completion/`

Private report:

`TOSEM_CORE_COMPLETION_REPORT.md`
