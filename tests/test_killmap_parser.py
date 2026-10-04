"""Unit tests for kill-map parsers using synthetic fixtures."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from killmap.parse import (  # noqa: E402
    Cell,
    KillReason,
    compare_ab,
    load_test_map,
    parse_test_name,
    route_a_cells,
    route_b_cells_from_kill_csv,
)
from killmap.junit_methods import methods_from_java  # noqa: E402


def test_parse_test_name():
    a = parse_test_name("pkg.Foo[bar]")
    assert a.d4j == "pkg.Foo::bar"
    b = parse_test_name("pkg.Foo::bar")
    assert a == b
    assert a.major == "pkg.Foo[bar]"


def test_route_a_semantics(tmp_path: Path):
    (tmp_path / "testMap.csv").write_text(
        "TestNo,TestName,Runtime\n1,p.T[a],1\n2,p.T[b],1\n"
    )
    (tmp_path / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n1,2\n2,1\n")
    (tmp_path / "killMap.csv").write_text(
        "TestNo,MutantNo,[FAIL | TIME | EXC]\n1,1,FAIL\n"
    )
    tmap = load_test_map(tmp_path / "testMap.csv")
    cells = route_a_cells(tmp_path / "covMap.csv", tmp_path / "killMap.csv", 2, tmap)
    assert cells[(1, 1)] == (Cell.KILLED, KillReason.FAIL)
    assert cells[(1, 2)] == (Cell.SURVIVES, KillReason.LIVE)
    assert cells[(2, 1)] == (Cell.SURVIVES, KillReason.LIVE)
    assert cells[(2, 2)] == (Cell.NOT_COVERED, KillReason.UNCOV)


def test_route_b_and_compare(tmp_path: Path):
    (tmp_path / "testMap.csv").write_text(
        "TestNo,TestName,Runtime\n1,p.T[a],1\n"
    )
    (tmp_path / "covMap.csv").write_text("TestNo,MutantNo\n1,1\n")
    (tmp_path / "killMap.csv").write_text(
        "TestNo,MutantNo,[FAIL | TIME | EXC]\n1,1,FAIL\n"
    )
    tmap = load_test_map(tmp_path / "testMap.csv")
    a = route_a_cells(tmp_path / "covMap.csv", tmp_path / "killMap.csv", 1, tmap)
    bcsv = tmp_path / "kill.csv"
    bcsv.write_text("MutantNo,[FAIL | TIME | EXC | LIVE | UNCOV]\n1,FAIL\n")
    b_one = route_b_cells_from_kill_csv(bcsv)
    tid = tmap[1]
    b = {(tid, 1): b_one[1]}
    r = compare_ab(a, b, tmap)
    assert r["identical"] == 1
    assert r["cell_mismatch"] == 0


def test_junit_methods():
    src = """
public class Foo {
  public void testA() {}
  public void TestLang747() {}
  @Test
  public void testB() {}
  public void helper() {}
}
"""
    assert methods_from_java(src) == ["testA", "TestLang747", "testB"]


if __name__ == "__main__":
    import tempfile

    test_parse_test_name()
    with tempfile.TemporaryDirectory() as d:
        test_route_a_semantics(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_route_b_and_compare(Path(d))
    test_junit_methods()
    print("ok")
