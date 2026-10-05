# Data schema (SCHEMA_VERSION = 1)

Tables (Parquet under `results/derived/schema_v1/`):

- `bugs.parquet`
- `tests.parquet`
- `mutants.parquet`
- `cells.parquet`
- `provenance.json`

## cells semantics

Absent `(test_id, mutant_id)` means **not covered**.
Present with `test_covers_mutant=true` and `test_kills_mutant=false` means covered but survives (`kill_reason=LIVE`).
Present with `test_kills_mutant=true` means killed (`FAIL`/`TIME`/`EXC`).

## Provenance fields

`d4j_version`, `d4j_sha`, `major_version`, artifact `git_commit`, `generated_at`, per-source SHA-256 hashes.
