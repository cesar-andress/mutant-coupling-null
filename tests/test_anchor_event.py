"""Synthetic unique-kill checks for the historical coupling event."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coupling.anchor import TestId, anchor_from_maps  # noqa: E402
from killmap.parse import parse_test_name  # noqa: E402


def test_unique_kill(tmp_path: Path) -> None:
    (tmp_path / "testMap.csv").write_text(
        "TestNo,TestName,Runtime\n"
        "1,p.T[trig],1\n"
        "2,p.T[other],1\n"
    )
    (tmp_path / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n2,2\n1,2\n")
    (tmp_path / "killMap.csv").write_text(
        "TestNo,MutantNo,[FAIL | TIME | EXC]\n1,1,FAIL\n2,2,FAIL\n"
    )
    (tmp_path / "mutants.log").write_text("1:A\n2:B\n")
    row = anchor_from_maps("P", "1", tmp_path, [parse_test_name("p.T::trig")])
    assert row.coupled is True
    assert row.n_unique_trigger == 1
    assert row.trigger_adds_coverage is True


def test_no_unique(tmp_path: Path) -> None:
    (tmp_path / "testMap.csv").write_text(
        "TestNo,TestName,Runtime\n1,p.T[trig],1\n2,p.T[other],1\n"
    )
    (tmp_path / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n2,1\n")
    (tmp_path / "killMap.csv").write_text(
        "TestNo,MutantNo,[FAIL | TIME | EXC]\n1,1,FAIL\n2,1,FAIL\n"
    )
    (tmp_path / "mutants.log").write_text("1:A\n")
    row = anchor_from_maps("P", "1", tmp_path, [parse_test_name("p.T::trig")])
    assert row.coupled is False
    assert row.n_unique_trigger == 0


if __name__ == "__main__":
    import tempfile
    for fn in (test_unique_kill, test_no_unique):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    print("ok")
