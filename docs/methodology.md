# Methodology (placeholder)

Intended, not executed:

1. For each selected Defects4J bug on the fixed version, obtain a test-by-mutant kill matrix.
2. Identify official fault-triggering tests.
3. Score the historical unique-kill coupling criterion on trigger tests.
4. Score the same leave-one-test-out unique-kill criterion on ordinary non-trigger tests.
5. Match or stratify on coverage gain.
6. Optionally classify mutant locality relative to the real patch and join trigger-test provenance.

No artifact is repaired. No model is prompted. No oracle-feedback loop.

Do not run this protocol until the parent project gates authorize it.
