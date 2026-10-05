"""T9 matching: frozen exposure bins and within-bug, within-stratum matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


def exposure_bin(n_mutants_covered: int) -> int:
    n = int(n_mutants_covered)
    if n <= 0:
        return 0
    if n <= 5:
        return 1
    if n <= 20:
        return 2
    if n <= 50:
        return 3
    if n <= 200:
        return 4
    return 5


def test_class(test_id: str) -> str:
    return test_id.split("::", 1)[0]


@dataclass(frozen=True)
class Matchable:
    test_id: str
    event: bool
    n_mutants_covered: int
    coverage_gain: bool
    is_trigger: bool


def match_placebos(trigger: Matchable, placebos: Sequence[Matchable]) -> List[Matchable]:
    """Return matched placebos under the locked rule. Empty = unmatched."""
    tbin = exposure_bin(trigger.n_mutants_covered)
    same_bin = [
        p
        for p in placebos
        if (not p.is_trigger)
        and p.coverage_gain == trigger.coverage_gain
        and exposure_bin(p.n_mutants_covered) == tbin
    ]
    tclass = test_class(trigger.test_id)
    same_class = [p for p in same_bin if test_class(p.test_id) == tclass]
    if same_class:
        return same_class
    return list(same_bin)


def bug_rates(triggers: Iterable[Matchable], placebos: Sequence[Matchable]) -> Optional[dict]:
    matched_t = []
    pair_placebo_means = []
    used_placebos = set()
    for t in triggers:
        ms = match_placebos(t, placebos)
        if not ms:
            continue
        matched_t.append(t)
        pair_placebo_means.append(sum(p.event for p in ms) / len(ms))
        used_placebos.update(p.test_id for p in ms)
    if not matched_t:
        return None
    r_trig = sum(t.event for t in matched_t) / len(matched_t)
    r_plac = sum(pair_placebo_means) / len(pair_placebo_means)
    return {
        "n_trigger_matched": len(matched_t),
        "n_placebo_matched_unique": len(used_placebos),
        "r_trigger": r_trig,
        "r_placebo": r_plac,
        "excess": r_trig - r_plac,
    }
