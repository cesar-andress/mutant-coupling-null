# mutant-coupling-null

Research artifact under active development. Not a published paper. No results exist yet.

## Scientific question

Does a fault-triggering test satisfy the historical mutant–real-fault coupling criterion more often than a comparable ordinary non-triggering test?

The primary estimand is **excess coupling**: the coupling rate among fault-triggering tests minus the coupling rate among coverage-matched non-trigger tests, on the same mutant kill matrices.

## Status

- Local overlap gate: PASS
- Global novelty / scoop gate: PARTIAL (scientifically distinct; see the parent project audit)
- Environment smoke (T3): pinned Defects4J 3.0.1 / Java 11 / Major 3.0.1
- MVP: NOT STARTED
- Full study: NOT AUTHORIZED
- Anchor reproduction: NOT claimed (stock mutation only; no kill map)

## Reproduce the environment smoke

Requires Docker, network only for the image build (open-source downloads).

```
./scripts/run_t3_smoke.sh
```

Details: `docs/environment.md`. Outputs of class `results/raw/smoke/` (manifest tracked; bulky logs ignored).

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

## Author

**César Andrés** (corresponding author)  
ORCID: [0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404)  
Email: cesar.andress@ucjc.edu  
Affiliation: CRIA-BDHS Research Group, Escuela Politécnica Superior de Tecnología y Ciencia, Universidad Camilo José Cela, Spain

Machine-readable metadata: `CITATION.cff` and `.zenodo.json`.

## Cite this artifact

Until Zenodo assigns a DOI, cite the GitHub repository and the version in `CITATION.cff` (currently 0.1.2). Do not invent a DOI.

## Zenodo

This GitHub repository is the canonical software source for a Zenodo deposit.

1. On [Zenodo](https://zenodo.org), enable GitHub integration for `cesar-andress/mutant-coupling-null`.
2. When a deposit is authorized, create a GitHub Release from a hygiene-checked tag.
3. Put the version DOI into `CITATION.cff` after Zenodo mints it.

Do not redistribute Defects4J or Major in the deposit. `.zenodo.json` is the deposit metadata template. See `docs/zenodo.md`.
