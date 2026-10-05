"""Synthetic placebo/event engine cases."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from placebo.engine import build_events  # noqa: E402


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_cases():
    # CASE 1: trigger unique; placebos share kills (need ≥2 placebos)
    tests = ["t", "p", "q"]
    covers = {"t": {1}, "p": {2}, "q": {2}}
    kills = {"t": {1}, "p": {2}, "q": {2}}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(by["t"].event and not by["p"].event and not by["q"].event, "case1")

    # CASE 2: placebo unique, trigger none
    kills = {"t": {2}, "p": {1}, "q": {2}}
    covers = {"t": {2}, "p": {1}, "q": {2}}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(not by["t"].event and by["p"].event, "case2")

    # CASE 3: both
    kills = {"t": {1}, "p": {3}, "q": {2}}
    covers = {"t": {1}, "p": {3}, "q": {2}}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(by["t"].event and by["p"].event, "case3")

    # CASE 4: neither (shared kill)
    kills = {"t": {1}, "p": {1}, "q": {1}}
    covers = {"t": {1}, "p": {1}, "q": {1}}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(not by["t"].event and not by["p"].event, "case4")

    # CASE 5: coverage gain causes unique kill
    tests = ["t", "a", "b"]
    covers = {"t": {1, 2}, "a": {1}, "b": {1}}
    kills = {"t": {2}, "a": set(), "b": set()}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(by["t"].coverage_gain and by["t"].event, "case5")

    # CASE 6: unique kill without coverage gain
    covers = {"t": {1}, "a": {1}, "b": {1}}
    kills = {"t": {1}, "a": set(), "b": set()}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(not by["t"].coverage_gain and by["t"].event, "case6")

    # CASE 7: multiple triggers never enter base
    tests = ["t1", "t2", "p"]
    kills = {"t1": {1}, "t2": {1}, "p": set()}
    covers = {"t1": {1}, "t2": {1}, "p": set()}
    rows = build_events("P", "1", tests, {"t1", "t2"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(by["t1"].event and by["t2"].event, "case7")

    # CASE 8: multiple placebo
    tests = ["t", "p1", "p2"]
    kills = {"t": {1}, "p1": {2}, "p2": {3}}
    covers = kills
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    _assert(sum(r.event for r in rows if not r.is_trigger) == 2, "case8")

    # CASE 9: timeout-as-kill is just membership in kill set
    kills = {"t": {1}, "p": set()}
    covers = {"t": {1}, "p": {1}}
    rows = build_events("P", "1", ["t", "p"], {"t"}, covers, kills)
    _assert(rows[0].event, "case9")

    # CASE 10: uncovered
    covers = {"t": set(), "p": set()}
    kills = {"t": set(), "p": set()}
    rows = build_events("P", "1", ["t", "p"], {"t"}, covers, kills)
    _assert(not any(r.event for r in rows), "case10")

    # CASE 11: later test erases older uniqueness
    tests = ["old", "new", "t"]
    kills = {"old": {1}, "new": {1}, "t": {2}}
    covers = kills
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    by = {r.test_id: r for r in rows}
    _assert(not by["old"].event and by["t"].event, "case11")

    # CASE 12: planted excess coupling
    tests = ["t", "p1", "p2", "p3"]
    kills = {"t": {9}, "p1": {1}, "p2": {1}, "p3": {1}}
    covers = {"t": {9}, "p1": {1}, "p2": {1}, "p3": {1}}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    trig = [r for r in rows if r.is_trigger]
    plac = [r for r in rows if not r.is_trigger]
    _assert(all(r.event for r in trig) and not any(r.event for r in plac), "case12")

    for r in rows:
        _assert(r.is_trigger or r.eligible_for_primary_placebo, "elig")
        _assert(r.event == (r.n_unique_kills > 0), "binary")


def test_not_degenerate():
    tests = [f"p{i}" for i in range(10)] + ["t"]
    covers = {t: {i % 5} for i, t in enumerate(tests)}
    kills = {t: ({i % 5} if i % 3 == 0 else set()) for i, t in enumerate(tests)}
    kills["t"] = {99}
    covers["t"] = {99}
    rows = build_events("P", "1", tests, {"t"}, covers, kills)
    plac = [r for r in rows if not r.is_trigger]
    rates = [r.event for r in plac]
    _assert(any(rates) and not all(rates), "nondegenerate placebo")
    _assert(any(r.coverage_gain for r in rows) and any(not r.coverage_gain for r in rows), "gain varies")


if __name__ == "__main__":
    test_cases()
    test_not_degenerate()
    print("ok")
