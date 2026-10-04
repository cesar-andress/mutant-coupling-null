#!/usr/bin/env python3
"""Consistency checks on an existing Route A/B compare.json."""

import json
import sys
from pathlib import Path


def check(path: Path) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["method_level"] is True
    assert d["cell_mismatch"] == 0
    assert d["missing_in_b"] == 0
    assert d["n_tests_a"] > 0
    assert d["n_mutants"] > 0
    print("ok", path, "identical", d["identical"])


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    files = list(root.glob("results/raw/t4/**/compare.json"))
    if not files:
        print("no compare.json yet")
        sys.exit(0)
    for f in files:
        check(f)
