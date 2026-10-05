"""Parameterized IDs remain distinct through maps → ETL → events (if raw Math-3 exists)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from etl.ingest import ingest_bug  # noqa: E402
from killmap.parse import load_test_map  # noqa: E402
from placebo.engine import build_events  # noqa: E402


def test_math3_parameterized_pipeline():
    d = ROOT / "results" / "raw" / "t5" / "Math-3"
    if not (d / "testMap.csv").is_file():
        return
    tmap = load_test_map(d / "testMap.csv")
    nested = [t for t in tmap.values() if t.decoration]
    assert nested, "expected parameterized identities in Math-3"
    canons = [t.canonical for t in tmap.values()]
    assert len(canons) == len(set(canons))
    trig = d / "trigger_tests.txt"
    bugs, tests, muts, cells, _ = ingest_bug(
        "Math", "3", d, trig, "3.0.1", "6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09", "3.0.1"
    )
    ids = [t["test_id"] for t in tests]
    assert len(ids) == len(set(ids))
    covers = {t["test_id"]: set() for t in tests}
    kills = {t["test_id"]: set() for t in tests}
    for c in cells:
        covers[c["test_id"]].add(c["mutant_id"])
        if c["test_kills_mutant"]:
            kills[c["test_id"]].add(c["mutant_id"])
    triggers = {t["test_id"] for t in tests if t["is_trigger"]}
    rows = build_events("Math", "3", ids, triggers, covers, kills)
    assert len(rows) == len(ids)
    deco_rows = [r for r in rows if "[" in r.test_id.split("::", 1)[-1]]
    assert deco_rows
    assert len({r.test_id for r in deco_rows}) == len(deco_rows)
