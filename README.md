# mutant-coupling-null

Replication artifact (v1.0.0) for a Defects4J 3.0.1 / Major 3.0.1 study of mutant–real-fault coupling with an ordinary-test reference arm.

The LaTeX manuscript lives in a private companion repository.

## Scientific question

How much more often do fault-triggering tests satisfy the historical mutant–real-fault coupling event than comparable ordinary non-triggering tests?

The primary estimand is **excess coupling**: the mean bug-level difference between matched trigger and ordinary unique-kill rates in the NO_GAIN stratum.

Frozen primary result (n = 288): trigger 0.649, ordinary reference 0.227, excess 0.423, 95% CI [0.362, 0.481].

## Reproduce manuscript outputs

Follow `REPRODUCIBILITY.md`. In short: check out tag `v1.0.0`, download the GitHub Release canonical-map archive, verify its SHA-256, unpack it, then run:

```
python3.12 scripts/run_full_study_analysis.py .
python3.12 scripts/verify_primary_summary.py
python3.12 scripts/run_tosem_core_completion.py .
python3.12 scripts/generate_manuscript_tables.py .
```

Protocol locks: `docs/protocol/`. Data package notes: `docs/data_package.md`.

Full mutation acquisition (`scripts/full_study_campaign.py`) is closed.

## Environment smoke

Requires Docker. `./scripts/run_t3_smoke.sh` — details in `docs/environment.md`.

## What this repository is

Original analysis code, configs, tests, frozen derived tables, and protocol locks for the ordinary-test reference-rate study.

## What this repository is not

- It does not redistribute Defects4J or Major source trees.
- It does not contain confidential data.
- It does not claim journal acceptance.
- It does not contain the LaTeX manuscript.

## Licenses

| Material | License |
|----------|---------|
| Original code and documentation in this repository | MIT (see `LICENSE`) |
| Third-party tools and benchmark source | remain under their upstream licenses |
| Generated canonical kill maps (Release asset) | study outputs; see `docs/data_package.md` |

## Author

**César Andrés** (corresponding author)  
ORCID: [0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404)  
Email: cesar.andress@ucjc.edu  
Affiliation: CRIA-BDHS Research Group, Escuela Politécnica Superior de Tecnología y Ciencia, Universidad Camilo José Cela, Spain

Machine-readable metadata: `CITATION.cff` and `.zenodo.json`.

## Cite this artifact

Until Zenodo assigns a DOI, cite the GitHub repository and version **1.0.0**. Do not invent a DOI.
