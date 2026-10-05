"""Synthetic tests for locked T9 matching (no real-effect peeking)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvp.matching import Matchable, bug_rates, exposure_bin, match_placebos  # noqa: E402
from mvp.bootstrap import percentile_ci  # noqa: E402


def test_exposure_bins():
    assert exposure_bin(0) == 0
    assert exposure_bin(5) == 1
    assert exposure_bin(6) == 2
    assert exposure_bin(21) == 3
    assert exposure_bin(200) == 4
    assert exposure_bin(201) == 5


def test_same_class_preferred():
    t = Matchable("a.T::trig", True, 3, False, True)
    p_other = Matchable("b.U::p", False, 3, False, False)
    p_same = Matchable("a.T::p", True, 4, False, False)
    ms = match_placebos(t, [p_other, p_same])
    assert [m.test_id for m in ms] == ["a.T::p"]


def test_bin_fallback_and_unmatched():
    t = Matchable("a.T::trig", True, 3, False, True)
    far = Matchable("a.T::p", False, 300, False, False)
    assert match_placebos(t, [far]) == []
    near = Matchable("b.U::p", False, 2, False, False)
    assert match_placebos(t, [near])[0].test_id == "b.U::p"


def test_planted_excess():
    trigs = [Matchable("a.T::t", True, 3, False, True)]
    plac = [
        Matchable("a.T::p1", False, 3, False, False),
        Matchable("a.T::p2", False, 4, False, False),
    ]
    r = bug_rates(trigs, plac)
    assert r is not None
    assert r["r_trigger"] == 1.0
    assert r["r_placebo"] == 0.0
    assert r["excess"] == 1.0


def test_bootstrap_reproducible():
    a = percentile_ci([0.1, 0.2, 0.3], n_resamples=200, seed=1)
    b = percentile_ci([0.1, 0.2, 0.3], n_resamples=200, seed=1)
    assert a[0] == b[0]
    assert a[1] == b[1]
    assert a[2] == b[2]
