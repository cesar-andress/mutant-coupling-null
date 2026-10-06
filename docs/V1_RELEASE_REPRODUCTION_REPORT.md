# v1.0.0 fresh-clone reproduction report

Date (UTC): 2026-10-06  
Clone tested: `2e392a95628cf16157a18ec0c2720e09dc2d42c4` (`origin/main` at test time)  
Host: temporary directory `/tmp/mcn-fresh-v1` (outside both canonical repositories)  
Inputs used: Git clone of `cesar-andress/mutant-coupling-null` + Release archive  
`mutant-coupling-null-canonical-data-v1.0.0.tar.gz`  
Archive SHA-256: `3553a6c3fefcef44de4b1094fb7bfc4db44a32fc5e18a51da5b8bedd243ed636`  
Author-local maps, caches, and `/home/cesar/papers/...` source files were **not** used.

## Commands and runtime

Python 3.12 venv with `numpy scipy statsmodels matplotlib pytest`.

| Step | Command | Wall time |
|---|---|---|
| Unpack 481 maps | `python scripts/unpack_canonical_maps.py mutant-coupling-null-canonical-data-v1.0.0.tar.gz --dest results/raw/t5` | included in setup |
| Primary analysis | `python scripts/run_full_study_analysis.py .` | 11 s |
| Primary verify | `python scripts/verify_primary_summary.py` | <1 s (`PRIMARY_OK`) |
| Core-completion robustness | `python scripts/run_tosem_core_completion.py .` | 32 s |
| Manuscript tables/figures | `python scripts/generate_manuscript_tables.py .` | <1 s |
| Public tests | `python -m pytest -q` | 1.11 s, **38 passed** |
| **Total including clone/venv** | | **60 s** |

## Primary scalars reproduced

Frozen lock vs recomputed `results/derived/full_study/primary_summary.json`:

| Quantity | Frozen | Fresh clone |
|---|---|---|
| N | 288 | 288 |
| trigger rate | 0.6493827160493827 | 0.6493827160493827 |
| reference rate | 0.2266392522911936 | 0.2266392522911935 |
| excess | 0.4227434637581891 | 0.4227434637581892 |
| 95% CI | [0.3624604432266677, 0.48129122021336346] | [0.3624604432266676, 0.4812912202133638] |

Differences are IEEE rounding at \(\le 10^{-15}\) and pass `verify_primary_summary.py` (tolerance \(10^{-12}\)).

## Also regenerated

- Robustness: `results/derived/full_study/core_completion/` (including equal-project-weight 0.436).
- Manuscript table: `results/derived/full_study/manuscript_export/tables/tab_rq1_primary.tex`.
- Manuscript figures: `fig_rq1_paired_rates.png`, `fig_project_forest.png`.

## Verdict

PASS. The released 481-map archive plus tracked source reproduces the locked primary result.
