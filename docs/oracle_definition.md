# Oracle / criterion definition

The historical coupling event used by this project:

A real fault is counted as coupled when adding its fault-triggering test causes the suite to kill at least one mutant it did not kill before (unique kill).

The placebo event uses the same unique-kill criterion on a matched non-triggering test.

This file will later freeze operational rules (leave-one-test-out, coverage-gain matching, locality labels, provenance labels). Those rules are not executed yet.
