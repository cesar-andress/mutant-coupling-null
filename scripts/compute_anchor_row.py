#!/usr/bin/env python3
"""Compute historical unique-kill coupling from Route A maps + trigger list."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, "/opt/artifact/src")

from coupling.anchor import AnchorRow, anchor_from_maps, load_trigger_ids  # noqa: E402


def triggers_from_d4j_file(path: Path) -> list:
    from killmap.parse import parse_test_name

    ids = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- "):
            ids.append(parse_test_name(line[4:].strip()))
    return ids


def main() -> int:
    project, bid, a_dir, trigger_src, out = sys.argv[1:6]
    a_dir = Path(a_dir)
    tpath = Path(trigger_src)
    if tpath.name == "triggers.txt" or tpath.suffix == ".txt" and not tpath.read_text()[:4] == "--- ":
        try:
            trig = load_trigger_ids(tpath)
        except Exception:
            trig = triggers_from_d4j_file(tpath)
    else:
        trig = triggers_from_d4j_file(tpath)
    row = anchor_from_maps(project, bid, a_dir, trig)
    Path(out).write_text(json.dumps(asdict(row), indent=2) + "\n")
    print(json.dumps(asdict(row)))
    return 0 if row.exclusion_reason is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
