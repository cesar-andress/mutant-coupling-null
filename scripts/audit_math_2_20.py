#!/usr/bin/env python3
"""Classify Math 1–20 T5 jobs from raw outputs. No mutation rerun."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coupling.anchor import validate_anchor  # noqa: E402
from killmap.parse import load_test_map  # noqa: E402


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace").strip() if p.is_file() else ""


def _time_wall(p: Path) -> str:
    if not p.is_file():
        return ""
    for line in p.read_text(errors="replace").splitlines():
        if line.startswith("wall_sec="):
            return line.split("=", 1)[1]
        if line.startswith("elapsed_epoch_sec="):
            return line.split("=", 1)[1]
    return ""


def classify(d: Path, bid: int) -> dict:
    maps = all((d / n).is_file() for n in ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log"))
    anchor_p = d / "anchor.json"
    mut_exit = _read(d / "mutation.exit")
    mut_err = _read(d / "mutation.stderr")
    parser_status = "n/a"
    if maps:
        try:
            load_test_map(d / "testMap.csv")
            parser_status = "ok"
        except Exception as exc:  # noqa: BLE001 — status recording
            parser_status = f"fail:{type(exc).__name__}"
    coupled = None
    exclusion = None
    if anchor_p.is_file():
        doc = json.loads(anchor_p.read_text())
        v = validate_anchor(doc, require_provenance=False)
        coupled = bool(doc.get("coupled"))
        exclusion = doc.get("exclusion_reason")
        if v:
            final = "OTHER"
            reason = "anchor_schema:" + ";".join(v)
        elif exclusion:
            final = "OTHER"
            reason = str(exclusion)
        elif coupled:
            final = "COMPLETE_COUPLED"
            reason = "valid_anchor"
        else:
            final = "COMPLETE_UNCOUPLED"
            reason = "valid_anchor"
    elif maps and parser_status.startswith("fail"):
        final = "PARSER_FAILURE"
        reason = parser_status
    elif maps:
        final = "MISSING_OUTPUT"
        reason = "maps_present_anchor_absent"
    elif mut_exit not in ("", "0"):
        final = "MUTATION_FAILURE"
        reason = f"mutation.exit={mut_exit}"
    elif "mutation.test" in mut_err and "OK" not in mut_err.split("mutation.test")[-1]:
        final = "TIMEOUT"
        reason = "watchdog_or_interrupt_during_mutation.test_1800s"
    elif not d.exists() or (d.exists() and not any(d.iterdir())):
        final = "NOT_COMPLETED"
        reason = "no_outputs"
    else:
        final = "NOT_COMPLETED"
        reason = "incomplete_without_maps"
    return {
        "project": "Math",
        "bug_id": str(bid),
        "checkout_exit": _read(d / "checkout.exit") or None,
        "compile_exit": _read(d / "compile.exit") or None,
        "tests_exit": _read(d / "tests.exit") or None,
        "mutation_exit": mut_exit or None,
        "mutation_wall_sec": _time_wall(d / "mutation.time") or None,
        "raw_maps_present": maps,
        "anchor_json_present": anchor_p.is_file(),
        "parser_status": parser_status,
        "coupled": coupled,
        "classification": final,
        "reason": reason,
        "timeout_policy_sec": 1800,
        "job_return_code": None,
    }


# Docker rc values recorded in the Math 2–20 overnight log (UTC 2026-10-05).
LOGGED_RC = {
    2: 0,
    3: 1,
    4: 0,
    5: 1,
    9: 0,
    10: 124,
    12: 0,
    16: 124,
}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    raw = root / "results" / "raw" / "t5"
    rows = []
    for bid in range(1, 21):
        row = classify(raw / f"Math-{bid}", bid)
        if bid in LOGGED_RC:
            row["job_return_code"] = LOGGED_RC[bid]
            if LOGGED_RC[bid] == 124:
                row["classification"] = "TIMEOUT"
                row["reason"] = "timeout_1800s_rc=124"
        rows.append(row)
    out = root / "results" / "derived" / "math_2_20"
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(json.dumps({"bugs": rows}, indent=2) + "\n")
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    print(json.dumps({"n": len(rows), "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
