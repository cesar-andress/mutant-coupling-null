"""Regression tests for parameterized / nested Major test identities."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from killmap.parse import (  # noqa: E402
    CanonicalIdCollisionError,
    load_test_map,
    parse_test_name,
)


def test_class_method_major_and_d4j_equivalent():
    a = parse_test_name("pkg.Foo[bar]")
    b = parse_test_name("pkg.Foo::bar")
    assert a == b
    assert a.canonical == "pkg.Foo::bar"
    assert a.method == "bar"
    assert a.decoration == ""
    assert a.major == "pkg.Foo[bar]"


def test_class_only():
    t = parse_test_name("org.example.FooTest")
    assert t.class_name == "org.example.FooTest"
    assert t.method == ""
    assert t.canonical == "org.example.FooTest"


def test_parameterized_math3_form():
    raw = (
        "org.apache.commons.math3.analysis.integration.gauss."
        "HermiteParametricTest[testAllMonomials[2]]"
    )
    t = parse_test_name(raw)
    assert t.class_name.endswith("HermiteParametricTest")
    assert t.method == "testAllMonomials"
    assert t.decoration == "[2]"
    assert t.canonical.endswith("::testAllMonomials[2]")
    assert t.raw == raw


def test_parameterized_math5_form():
    raw = "org.apache.commons.math3.transform.FastCosineTransformerTest[testSinFunction[0]]"
    t = parse_test_name(raw)
    assert t.method == "testSinFunction"
    assert t.decoration == "[0]"
    assert "[0]" in t.canonical


def test_nested_and_sibling_brackets():
    t = parse_test_name("pkg.T[foo[0][bar]]")
    assert t.method == "foo"
    assert t.decoration == "[0][bar]"
    u = parse_test_name("pkg.T::foo[0][bar]")
    assert t == u


def test_distinct_indices_do_not_collapse():
    a = parse_test_name("pkg.T[m[0]]")
    b = parse_test_name("pkg.T[m[1]]")
    c = parse_test_name("pkg.T[m]")
    assert len({a, b, c}) == 3
    assert a.canonical != b.canonical
    assert a.method == b.method == "m"


def test_stripping_decoration_would_collide_but_parser_does_not():
    a = parse_test_name("pkg.T[m[0]]")
    b = parse_test_name("pkg.T[m[1]]")
    stripped = {a.method, b.method}
    assert stripped == {"m"}
    assert a.canonical != b.canonical


def test_malformed_and_empty_method():
    with pytest.raises(ValueError):
        parse_test_name("")
    with pytest.raises(ValueError):
        parse_test_name("pkg.T[]")
    with pytest.raises(ValueError):
        parse_test_name("pkg.T[")
    with pytest.raises(ValueError):
        parse_test_name("pkg.T[foo")
    with pytest.raises(ValueError):
        parse_test_name("::foo")
    with pytest.raises(ValueError):
        parse_test_name("pkg.T::")


def test_duplicate_canonical_ids_rejected(tmp_path: Path):
    p = tmp_path / "testMap.csv"
    p.write_text(
        "TestNo,TestName,Runtime\n"
        "1,pkg.T[m[0]],1\n"
        "2,pkg.T[m[0]],1\n"
    )
    with pytest.raises(CanonicalIdCollisionError):
        load_test_map(p)


def test_duplicate_testno_rejected(tmp_path: Path):
    p = tmp_path / "testMap.csv"
    p.write_text(
        "TestNo,TestName,Runtime\n"
        "1,pkg.T[a],1\n"
        "1,pkg.T[b],1\n"
    )
    with pytest.raises(ValueError, match="duplicate TestNo"):
        load_test_map(p)


def test_two_raw_forms_same_execution_are_equal():
    a = parse_test_name("pkg.T[m[2]]")
    b = parse_test_name("pkg.T::m[2]")
    assert a == b
    assert a.canonical == b.canonical
