#!/usr/bin/env python3
"""Assert frozen primary scalars in primary_summary.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXPECTED = {
    "n_primary_matched": 288,
    "r_trigger": 0.6493827160493827,
    "r_placebo": 0.2266392522911936,
    "excess": 0.4227434637581891,
    "ci_lo": 0.3624604432266677,
    "ci_hi": 0.48129122021336346,
}


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "results/derived/full_study/primary_summary.json")
    s = json.loads(path.read_text())
    assert s["n_primary_matched"] == EXPECTED["n_primary_matched"]
    for k in ("r_trigger", "r_placebo", "excess"):
        if abs(float(s[k]) - EXPECTED[k]) > 1e-12:
            raise SystemExit(f"mismatch {k}: {s[k]} vs {EXPECTED[k]}")
    lo, hi = s["ci95"]
    if abs(lo - EXPECTED["ci_lo"]) > 1e-12 or abs(hi - EXPECTED["ci_hi"]) > 1e-12:
        raise SystemExit(f"mismatch ci {s['ci95']}")
    print("PRIMARY_OK", s["n_primary_matched"], s["excess"], s["ci95"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
