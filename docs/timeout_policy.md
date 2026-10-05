# Timeout policy (T5 Route A)

`scripts/t5_run_project.sh` wraps each bug in `timeout 1800`
(1800 seconds wall). The overnight Math 2–20 job used the same wrapper.

This bound is **pre-specified**. It is not raised because a bug timed out.

A TIMEOUT classification means the watchdog killed the bug job. Partial
checkout/compile/test logs may exist; kill maps from an interrupted
`mutation.test` are **not** scientifically valid.

Retry: at most one automatic retry, and only for a documented deterministic
infrastructure fault (missing patch, wrong Python path). Timeout itself is
not such a fault. Math-10 and Math-16 are not retried in this stabilization
task.
