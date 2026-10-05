"""Placebo / unique-kill event engine (T8). No full MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class EventRow:
    project: str
    bug_id: str
    test_id: str
    is_trigger: bool
    event: bool
    n_unique_kills: int
    coverage_gain: bool
    n_mutants_covered: int
    local_unique_kills: int
    nonlocal_unique_kills: int
    eligible_for_primary_placebo: bool


def unique_kills(
    test_id: str,
    kills: Dict[str, Set[int]],
    base_tests: Iterable[str],
) -> Set[int]:
    base = set(base_tests)
    others_kills: Set[int] = set()
    for t in base:
        if t == test_id:
            continue
        others_kills |= kills.get(t, set())
    return set(kills.get(test_id, set())) - others_kills


def coverage_gain(
    test_id: str,
    covers: Dict[str, Set[int]],
    base_tests: Iterable[str],
) -> bool:
    base = set(base_tests)
    others: Set[int] = set()
    for t in base:
        if t == test_id:
            continue
        others |= covers.get(t, set())
    return bool(set(covers.get(test_id, set())) - others)


def build_events(
    project: str,
    bug_id: str,
    tests: Iterable[str],
    triggers: Set[str],
    covers: Dict[str, Set[int]],
    kills: Dict[str, Set[int]],
    locality: Optional[Dict[int, str]] = None,
) -> list:
    """Symmetric event: base = non-trigger tests; x removed from its own base."""
    nontrigger = [t for t in tests if t not in triggers]
    rows = []
    for t in tests:
        base = nontrigger  # triggers never in base
        uniq = unique_kills(t, kills, base)
        gain = coverage_gain(t, covers, base)
        local_u = nonloc_u = 0
        if locality is not None:
            for m in uniq:
                loc = locality.get(m, "MODIFIED_CLASS")
                if loc in ("PATCH_LINE", "PATCH_METHOD"):
                    local_u += 1
                else:
                    nonloc_u += 1
        else:
            nonloc_u = len(uniq)
        rows.append(
            EventRow(
                project=project,
                bug_id=bug_id,
                test_id=t,
                is_trigger=t in triggers,
                event=len(uniq) > 0,
                n_unique_kills=len(uniq),
                coverage_gain=gain,
                n_mutants_covered=len(covers.get(t, set())),
                local_unique_kills=local_u,
                nonlocal_unique_kills=nonloc_u,
                eligible_for_primary_placebo=(t not in triggers),
            )
        )
    return rows
