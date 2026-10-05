# Placebo / unique-kill event engine

Symmetric event definition (T8 validation only; not the MVP study):

- Base `B` = relevant non-trigger tests (triggers never enter `B`).
- For candidate test `x`, unique kill = mutant killed by `x` and by no test in `B \ {x}`.
- Event = at least one unique kill.
- Coverage gain = `x` covers a mutant not covered by `B \ {x}`.

Synthetic tests: `tests/test_placebo_engine.py`.

Small real validation (ENGINEERING_VALIDATION_ONLY):

```bash
python3.10 scripts/validate_placebo_small.py
```

Do not treat `results/derived/placebo_validation/` as paper results.
