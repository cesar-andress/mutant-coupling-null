# Anchor reproduction

Scripts:

- `scripts/t5_one_bug.sh` — Route A kill map + `anchor.json` for one bug
- `scripts/t5_run_project.sh` — all active bugs in a project
- `scripts/compute_anchor_row.py` — coupling row from existing maps

Event definition: a bug is coupled if a trigger test kills a mutant that no relevant non-trigger test kills.
