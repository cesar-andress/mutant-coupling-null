"""Historical unique-kill coupling (Just-style) from Route A maps. No placebo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from killmap.parse import Cell, KillReason, TestId, load_mutants_log, load_test_map, parse_test_name, route_a_cells


@dataclass
class AnchorRow:
    project: str
    bug_id: str
    n_trigger: int
    n_nontrigger: int
    n_mutants: int
    n_mutants_covered: int
    n_killed_by_base: int
    n_unique_trigger: int
    coupled: bool
    trigger_adds_coverage: bool
    exclusion_reason: Optional[str] = None


def load_trigger_ids(path: Path) -> List[TestId]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(parse_test_name(line))
    return out


def anchor_from_maps(
    project: str,
    bug_id: str,
    a_dir: Path,
    trigger_ids: List[TestId],
) -> AnchorRow:
    tmap = load_test_map(a_dir / "testMap.csv")
    mutants = load_mutants_log(a_dir / "mutants.log")
    n_mut = max(mutants)
    cells = route_a_cells(a_dir / "covMap.csv", a_dir / "killMap.csv", n_mut, tmap)
    by_name = {tid: n for n, tid in tmap.items()}
    missing = [t for t in trigger_ids if t not in by_name]
    if missing:
        return AnchorRow(
            project, bug_id, len(trigger_ids), 0, n_mut, 0, 0, 0, False, False,
            exclusion_reason="trigger_not_in_testmap:" + ",".join(t.d4j for t in missing),
        )
    trigger_nos = {by_name[t] for t in trigger_ids}
    nontrigger_nos = set(tmap) - trigger_nos
    # TIME and EXC count as kills (Major convention).
    def kills(tno: int, mid: int) -> bool:
        return cells[(tno, mid)][0] is Cell.KILLED

    def covers(tno: int, mid: int) -> bool:
        return cells[(tno, mid)][0] is not Cell.NOT_COVERED

    covered_muts = {m for t in tmap for m in range(1, n_mut + 1) if covers(t, m)}
    killed_by_base: Set[int] = set()
    covered_by_base: Set[int] = set()
    for t in nontrigger_nos:
        for m in range(1, n_mut + 1):
            if covers(t, m):
                covered_by_base.add(m)
            if kills(t, m):
                killed_by_base.add(m)
    unique = set()
    trig_cov = set()
    for t in trigger_nos:
        for m in range(1, n_mut + 1):
            if covers(t, m):
                trig_cov.add(m)
            if kills(t, m) and m not in killed_by_base:
                unique.add(m)
    adds_cov = bool(trig_cov - covered_by_base)
    return AnchorRow(
        project=project,
        bug_id=bug_id,
        n_trigger=len(trigger_nos),
        n_nontrigger=len(nontrigger_nos),
        n_mutants=n_mut,
        n_mutants_covered=len(covered_muts),
        n_killed_by_base=len(killed_by_base),
        n_unique_trigger=len(unique),
        coupled=len(unique) > 0,
        trigger_adds_coverage=adds_cov,
    )
