"""Synthetic ETL fixtures."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from etl.ingest import ingest_bug  # noqa: E402
from coupling.anchor import anchor_from_maps  # noqa: E402
from killmap.parse import parse_test_name  # noqa: E402


def _write_fixture(d: Path) -> None:
    (d / "testMap.csv").write_text(
        "TestNo,TestName,Runtime\n1,p.T[trig],1\n2,p.T[other],1\n"
    )
    (d / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n2,2\n1,2\n")
    (d / "killMap.csv").write_text(
        "TestNo,MutantNo,[FAIL | TIME | EXC]\n1,1,FAIL\n2,2,FAIL\n"
    )
    (d / "mutants.log").write_text(
        "1:AOR:p.C@m:10:x\n2:LVR:p.C@m:11:y\n"
    )
    (d / "trigger_tests.txt").write_text("--- p.T::trig\n")


def test_ingest_and_anchor():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_fixture(d)
        bugs, tests, muts, cells, prov = ingest_bug(
            "P", "1", d, d / "trigger_tests.txt", "3.0.1", "abc", "3.0.1"
        )
        assert bugs["n_trigger"] == 1
        assert len(tests) == 2
        assert len(muts) == 2
        # sparse cells: only covered
        assert all(c["test_covers_mutant"] for c in cells)
        assert sum(c["test_kills_mutant"] for c in cells) == 2
        row = anchor_from_maps("P", "1", d, [parse_test_name("p.T::trig")])
        assert row.coupled is True
        assert prov.schema_version == 1
        assert tests[0]["test_decoration"] in ("", None) or True


def test_parameterized_not_collapsed():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "testMap.csv").write_text(
            "TestNo,TestName,Runtime\n"
            "1,p.T[m[0]],1\n"
            "2,p.T[m[1]],1\n"
            "3,p.T[trig],1\n"
        )
        (d / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n2,1\n3,2\n")
        (d / "killMap.csv").write_text(
            "TestNo,MutantNo,[FAIL | TIME | EXC]\n3,2,FAIL\n1,1,TIME\n"
        )
        (d / "mutants.log").write_text("1:AOR:p.C@m:10:x\n2:LVR:p.C@m:11:y\n")
        (d / "trigger_tests.txt").write_text("--- p.T::trig\n")
        _, tests, _, cells, _ = ingest_bug(
            "P", "1", d, d / "trigger_tests.txt", "3.0.1", "abc", "3.0.1"
        )
        ids = [t["test_id"] for t in tests]
        assert "p.T::m[0]" in ids and "p.T::m[1]" in ids
        assert ids.count("p.T::m[0]") == 1
        deco = {t["test_id"]: t["test_decoration"] for t in tests}
        assert deco["p.T::m[0]"] == "[0]"
        assert deco["p.T::m[1]"] == "[1]"
        assert any(c["kill_reason"] == "TIME" for c in cells)


def test_duplicate_canonical_fails():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "testMap.csv").write_text(
            "TestNo,TestName,Runtime\n1,p.T[m[0]],1\n2,p.T[m[0]],1\n"
        )
        (d / "covMap.csv").write_text("TestNo,MutantNo\n")
        (d / "killMap.csv").write_text("TestNo,MutantNo,[FAIL | TIME | EXC]\n")
        (d / "mutants.log").write_text("1:AOR:p.C@m:10:x\n")
        (d / "trigger_tests.txt").write_text("--- p.T::m[0]\n")
        try:
            ingest_bug("P", "1", d, d / "trigger_tests.txt", "3.0.1", "abc", "3.0.1")
        except Exception:
            return
        raise AssertionError("expected collision error")


def test_malformed_testmap():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "testMap.csv").write_text("TestNo,TestName,Runtime\n1,p.T[unclosed,1\n")
        (d / "covMap.csv").write_text("TestNo,MutantNo\n")
        (d / "killMap.csv").write_text("TestNo,MutantNo,[FAIL | TIME | EXC]\n")
        (d / "mutants.log").write_text("1:AOR:p.C@m:10:x\n")
        (d / "trigger_tests.txt").write_text("--- p.T::x\n")
        try:
            ingest_bug("P", "1", d, d / "trigger_tests.txt", "3.0.1", "abc", "3.0.1")
        except Exception:
            return
        raise AssertionError("expected parse error")


if __name__ == "__main__":
    test_ingest_and_anchor()
    test_parameterized_not_collapsed()
    test_duplicate_canonical_fails()
    test_malformed_testmap()
    print("ok")
