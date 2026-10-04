# Reproduction

The environment smoke (`./scripts/run_t3_smoke.sh`) checks out Lang-1 FIXED, compiles, runs relevant tests, and runs stock `defects4j mutation -r`. It does not export a per-test kill map and does not compute coupling.

Until then:

- no kill matrices are stored here;
- no coupling estimates exist;
- third-party tools must not be assumed to be installed.
