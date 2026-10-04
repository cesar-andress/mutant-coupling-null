# mutant-coupling-null

Research artifact under active development. Not a published paper. No results exist yet.

## Scientific question

Does a fault-triggering test satisfy the historical mutant–real-fault coupling criterion more often than a comparable ordinary non-triggering test?

The primary estimand is **excess coupling**: the coupling rate among fault-triggering tests minus the coupling rate among coverage-matched non-trigger tests, on the same mutant kill matrices.

## Status

- Local overlap gate: PASS
- Global novelty / scoop gate: NOT YET PASSED
- MVP: NOT STARTED
- Full study: NOT AUTHORIZED

Reproduction instructions will be added after an authorized MVP.

## What this repository is

Original analysis code, configs, tests, and (later) derived tables for a chance-corrected test of mutant–real-fault coupling.

## What this repository is not

- It does not redistribute Defects4J, Major, or other third-party benchmarks.
- It does not contain confidential data.
- It does not claim publication or journal acceptance.
- It does not contain the LaTeX manuscript.

## Licenses

| Material | License |
|----------|---------|
| Original code and documentation in this repository | MIT (see `LICENSE`) |
| Third-party tools and benchmark data | remain under their upstream licenses |

MIT here does **not** relicense Defects4J, Major, or any other third-party corpus.

Acquisition notes: `data/README.md` and `external/`.

## Authors and archival identifiers

Author identity, ORCID, affiliation, and archival DOI are `HUMAN_REQUIRED`.
The intended public Git hosting identity is `cesar-andress/mutant-coupling-null`.
See `CITATION.cff` and `.zenodo.json`.
