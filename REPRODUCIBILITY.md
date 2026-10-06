# Reproducing the v1.0.0 results

This path uses **only** the Git tag `v1.0.0` and the GitHub Release data asset.
It does not require author-local files.

## 1. Clone the tag

```
git clone https://github.com/cesar-andress/mutant-coupling-null.git
cd mutant-coupling-null
git checkout v1.0.0
```

## 2. Download the canonical-map archive

From the GitHub Release `v1.0.0`, download:

`mutant-coupling-null-canonical-data-v1.0.0.tar.gz`

## 3. Verify checksum

```
sha256sum mutant-coupling-null-canonical-data-v1.0.0.tar.gz
```

Expected SHA-256:

```
3553a6c3fefcef44de4b1094fb7bfc4db44a32fc5e18a51da5b8bedd243ed636
```

## 4. Unpack into the documented location

```
python3.12 scripts/unpack_canonical_maps.py mutant-coupling-null-canonical-data-v1.0.0.tar.gz --dest results/raw/t5
```

This writes 481 canonical map directories (parser-excluded maps are not included).

## 5. Environment

Python 3.12 with: `numpy`, `scipy`, `statsmodels`, `matplotlib`, `pyarrow` (pyarrow optional for this path).

```
python3.12 -m venv .venv
. .venv/bin/activate
pip install numpy scipy statsmodels matplotlib
```

No GPU. No paid API.

## 6–10. Recompute primary summary, tables, and figures

```
python3.12 scripts/run_full_study_analysis.py .
python3.12 scripts/verify_primary_summary.py results/derived/full_study/primary_summary.json
python3.12 scripts/run_tosem_core_completion.py .
python3.12 scripts/generate_manuscript_tables.py .
```

Expected primary scalars (must match exactly):

- N = 288
- trigger rate = 0.6493827160493827
- ordinary reference rate = 0.2266392522911936
- excess = 0.4227434637581891
- 95% CI = [0.3624604432266677, 0.48129122021336346]

Tracked derived tables already in `results/derived/full_study/` are the frozen outputs.
The commands above recompute them from the released maps.

Protocol locks: `docs/protocol/`.
Data provenance: `docs/data_package.md`.
