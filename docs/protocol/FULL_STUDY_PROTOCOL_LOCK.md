# Full-study protocol lock

LOCKED_AT: 2026-10-05T10:30:00Z
LOCK_ID: FULL-STUDY-LOCK-20261005-V1
AUTHOR: César Andrés (ORCID 0009-0001-8968-3404)
PARENT_LOCKS:
- T9-MVP-LOCK-20261005-V1 (`9ab3effffd4b5f64d0892cf693e1fc4357eb03f3`)
- T9B-PRECISION-20261005-V1 (`c9947a5c0fe29bbbfcfad776a35821db38cacae2`)

STATUS: FROZEN before any previously unattempted full-study bug acquisition.

ENTRY GATE (verified before this lock):
- T9b FINAL MVP VERDICT = GO
- POST_OUTCOME_PRIMARY deviation count = 0

This file freezes the primary Defects4J 3.0.1 study. After SHA-256 and git
commit of this lock, acquisition of previously unattempted eligible bugs may
begin. Locked choices must not be changed after observing full-study outcomes
except as explicitly logged in `FULL_STUDY_PROTOCOL_DEVIATIONS.md`.

SHA-256 of this file: pending `sha256sum` immediately after write (recorded
below and in git).

## Resource probe (pre-acquisition)

Measured 2026-10-05T10:26+02 on the analysis host:

- Logical CPUs: 28
- CPU: Intel Core i7-14700K (1 socket)
- RAM: 125 GiB total; ~101 GiB available at probe
- Swap: 64 GiB (essentially unused)
- Disk free: 486 GiB on `/`
- Load averages: 2.72, 3.26, 3.11
- Container: `mutant-coupling-null:t3-env` (ubuntu:22.04, Java 11, Defects4J
  v3.0.1, Major 3.0.1)

T9/T9b concurrency: sequential (MAX_PARALLEL_BUGS = 1). Peak RSS on dense
Math maps historically reached ~13 GiB. Oversubscription can manufacture
timeouts; timeouts are scientific outcomes and must not be induced by
worker count.

**MAX_PARALLEL_BUGS = 3**

Rationale (resource, not effect): leave cores and RAM for the OS; keep
aggregate Java RSS well below available memory even if three dense maps
overlap; do not retune after seeing coupling estimates.

## Frozen items (1–30)

### 1. Benchmark version

Defects4J **v3.0.1**, git commit
`6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09`. Java 11. Major 3.0.1.
Validated T3–T9b pipeline. Docker image `mutant-coupling-null:t3-env`.

### 2. Full benchmark population

All **active** bugs in Defects4J 3.0.1 across the 17 supported projects:

Chart, Cli, Closure, Codec, Collections, Compress, Csv, Gson, JacksonCore,
JacksonDatabind, JacksonXml, Jsoup, JxPath, Lang, Math, Mockito, Time.

Enumerated count at freeze (from `active-bugs.csv` inside the pinned
checkout): **854**. Exact IDs: `results/derived/full_study/population_manifest.csv`.

Do not expand to another corpus. Do not drop projects because they are slow
or inconvenient.

### 3. Objective eligibility rules (pre-outcome)

A bug is **pre-outcome eligible** if and only if:

- it is listed in that project's `active-bugs.csv`;
- the fixed revision can be requested (`defects4j checkout -p PID -v BIDf`);
- `trigger_tests/<bug_id>` exists;
- `modified_classes` metadata exists for the bug;
- `relevant_tests/<bug_id>` exists;
- the validated mutation workflow (`defects4j mutation -r` + kill-map patch)
  applies.

At freeze, all 854 active bugs satisfy trigger, modified-class, and relevant-test
file presence. Completing mutation within the timeout is **not** eligibility.
Timeout is an execution outcome and remains in the sample flow.

### 4. Mutation scope

Fixed revision. Mutate Defects4J `classes.modified` (stock
`defects4j mutation -r`). Suite = relevant tests (`-r`). Do not expand to
loaded classes or the whole program after seeing results.

### 5. Mutation operators

Major `all.mml` as shipped with the pinned Defects4J Major 3.0.1, exactly:

AOR, LOR, SOR, COR, ROR, ORU, LVR, STD.

Do not add or remove operators in response to outcomes.

### 6. Trigger-test definition

Tests listed in Defects4J `trigger_tests/<bug_id>` for that active bug,
canonicalized with the frozen T8/parser test-ID grammar
(`Class::method[decoration]`).

### 7. Ordinary non-trigger definition

Every relevant-suite test in the kill map that is not a trigger test.
Trigger tests never enter the ordinary base. For an ordinary candidate `x`,
`x` is removed from its own base (T9 §5–6).

### 8. Relevant-test definition

Defects4J relevant tests for the bug (`defects4j mutation -r` / relevant
test list). No post-hoc suite editing.

### 9. Per-test matrix implementation

Route A: version-controlled patch
`acquire/patches/defects4j-major-killmap.patch`
(`exportKillMap="true"`, `testOrder=sort_methods`). Files:
`testMap.csv`, `covMap.csv`, `killMap.csv`, `mutants.log`.
Parser: `src/killmap/parse.py` (balanced-bracket parameterized IDs;
`CanonicalIdCollisionError` on collision). TIME and EXC count as kills
(T4/T5/T9).

### 10. Timeout policy

Per-bug wall timeout: **1800 seconds** (`docs/timeout_policy.md`, T9/T9b).
Do not increase timeout for difficult bugs. Do not retry TIMEOUT.

### 11. Treatment of technical failures

Classify and report:

PENDING, RUNNING, COMPLETE_VALID, TIMEOUT, BUILD_FAILURE,
MUTATION_FAILURE, PARSER_FAILURE, OTHER_FAILURE.

Isolated project/build failures continue. Stop the campaign only for a newly
discovered **global** defect that could invalidate already generated matrices
(test-ID collisions, mutant-ID corruption, wrong base-suite construction,
systematic trigger leakage, kill-map semantic inconsistency).

### 12. Primary event

For candidate test `x`:

`E(x) = 1` iff `x` kills at least one mutant that no test in the corresponding
ordinary non-trigger base kills.

Trigger tests never enter the ordinary base. For ordinary `x`, `x` is removed
from its own base. Implementation: `src/placebo/engine.py` `build_events`
(invert-index; T8-equivalent; D-T9-2).

### 13. Coverage-gain definition

`x` is COVERAGE_GAIN if it covers at least one mutant not covered by
`B \ {x}`; otherwise NO_GAIN (T9 §7).

### 14. Primary stratum

**NO_GAIN** is the headline stratum. COVERAGE_GAIN is secondary. Do not swap
after seeing results. Do not pool strata as the primary estimand.

### 15. Matching procedure

Exact T9 `src/mvp/matching.py`:

- within bug, within coverage-gain stratum;
- exposure bins on `n_mutants_covered`: 0 / 1–5 / 6–20 / 21–50 / 51–200 / 201+;
- same test class if any placebo exists in that (stratum, bin, class);
  otherwise all placebos in (stratum, bin);
- unmatched triggers omitted; bug omitted from primary if no NO_GAIN trigger
  is matched.

Do not retune bins.

### 16. Primary estimand

For each primary-eligible bug:

`Delta_b = R_trigger,b − R_reference,b`

where `R_reference` is the matched ordinary non-trigger mean as in T9
(`R_placebo` in code). Reported estimand: **mean bug-level excess coupling**
in NO_GAIN.

### 17. Primary inferential unit

**Bug**. Not tests, mutants, or cells.

### 18. Bootstrap / inference

Exact T9 `src/mvp/bootstrap.py`: resample bugs with replacement,
B = 10_000, seed = 20261005, 95% **percentile** interval of the mean excess.
Not cell/test bootstrap. Not outcome-driven switch to BCa or project
stratification. Optional labelled BCa remains a sensitivity only if SciPy is
already available; it is not the locked primary interval.

### 19. Locality definitions

T7 mapper levels: PATCH_LINE, PATCH_METHOD, MODIFIED_CLASS, ELSEWHERE.
Primary RQ2 contrast (T9 lock): unique-kill EVENT using only
PATCH_LINE ∪ PATCH_METHOD versus EVENT using only non-local unique kills,
same matching, on bugs with locality labels.
Roadmap contrast PATCH_METHOD versus rest of modified classes is reported
as an additional pre-specified RQ2 cut on the same mapper, not a redesign.

### 20. RQ2 analysis

Moderator only. Same matching and bug-level excess. Do not let RQ2 redefine
the main contribution.

### 21. Provenance categories

PRE_REPORT, POST_REPORT_MODIFIED, POST_REPORT_NEW, UNKNOWN.
Labels are information availability / chronology, **not** developer intent.
Rafi et al. coverage is an older Defects4J population; do not assume full
D4J 3.0.1 provenance. Use an explicit matched-subset mapping only.

### 22. RQ3 support gate

If fewer than 60% of relevant trigger observations receive a non-UNKNOWN
provenance label, **or** the PRE_REPORT stratum has fewer than 50 bugs
(roadmap stop rule), then RQ3 = SUPPLEMENTARY / INSUFFICIENT_SUPPORT.
Do not lower thresholds after observing results.

### 23. Recency sensitivity

If validated test chronology exists, construct the ordinary base for `x`
from tests available before `x`. If chronology is insufficient:
`RECENCY_SENSITIVITY_NOT_ESTIMABLE`. Do not invent timestamps.

### 24. Missing-data reporting

Timeouts and technical failures remain visible. No imputation of coupling
outcomes for missing bugs. Extreme-bound calculations, if produced, are
labelled BOUNDS / SENSITIVITY, not estimates.

### 25. Multiplicity treatment

Primary = one NO_GAIN mean-excess interval. COVERAGE_GAIN, RQ2, RQ3, recency,
and missingness bounds are secondary/sensitivity. No post-hoc promotion of a
secondary contrast to headline.

### 26. Precision target

Primary NO_GAIN 95% CI half-width ≤ 0.070: PASS / FAIL.
Because the population is the full eligible D4J 3.0.1 set, do **not** add
bugs outside this frozen benchmark to hit 0.070. Missing the target is a
limitation.

### 27. Acquisition policy

Attempt every pre-outcome eligible bug. Reuse all scientifically valid
T4/T5/T9/T9b matrices after schema/version checks. Frozen acquisition order:
sort eligible IDs by SHA-256 hex of
`FULL_STUDY_ACQ_v1_20261005:{project}:{bug_id}` (ascending). Already
attempted bugs (valid, timeout, or other terminal status) are not retried.
Do not stop, skip, or reorder based on accumulating effect estimates.

### 28. Parallel-execution policy

MAX_PARALLEL_BUGS = 3 independent Docker containers, `--network none`,
one bug per container, unique checkout directory. Do not retune workers
from scientific effects.

### 29. Retry policy

At most **one** retry after a deterministic infrastructure failure that is
clearly non-scientific, generally applicable, documented, and chosen without
using the bug's coupling outcome. Not allowed: retry until a desired valid
matrix appears. TIMEOUT is not retried.

### 30. Final analysis outputs

Private: `FULL_STUDY_REPORT.md`, `FULL_STUDY_PROTOCOL_DEVIATIONS.md`,
`KILL_REASON_FEASIBILITY.md`, `PIT_ROBUSTNESS_FEASIBILITY.md`.
Public (no private filesystem paths): `results/derived/full_study/` including
population manifest, campaign state, sample flow, canonical tables, primary
summary, project summary, locality/provenance/precision/compute artifacts,
and FINAL-CANDIDATE figures. Do not write manuscript Results, Abstract,
Discussion, or Conclusion in this task.

## Reuse rule

Reuse a matrix if it has `testMap.csv`, `covMap.csv`, `killMap.csv`,
`mutants.log`, trigger list, and collision-free parse under the current
parser. At freeze: **105** valid maps (Lang 58, Math 47). Lang-42/62/64
remain MUTATION_FAILURE. Math TIMEOUT bugs remain TIMEOUT.

## SOTA / scope exclusions

SOTA_SEARCH_STATUS = CLOSED_FOR_FULL_STUDY.
No second benchmark. PIT: feasibility only, ≤ 3 validation bugs, not a
population. No paid APIs. No GPU. No manuscript Results in this task.

## Protocol SHA-256

FILE_SHA256: `6202a99fc16839b4ffd6134a0f7ee6685f263db83cd601c436cab2df2c1d1412`
