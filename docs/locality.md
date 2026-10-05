# Mutant locality mapping

Deterministic labels relative to the Defects4J fix patch (T7):

- `PATCH_LINE` — mutant line appears in the unified-diff hunk
- `PATCH_METHOD` — mutant lies in a method that intersects the patch
- `MODIFIED_CLASS` — mutant class is among modified classes, outside patch methods
- `ELSEWHERE` — outside modified classes

Inputs: Defects4J `.src.patch`, checked-out fixed sources, Major `mutants.log` fields.

Usage:

```bash
python3.10 scripts/map_locality.py --help
```

Outputs: `results/derived/locality/`. No outcome-dependent tuning.
