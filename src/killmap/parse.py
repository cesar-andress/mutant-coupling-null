"""Parse Major / Defects4J mutation maps. No scientific filtering."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

class Cell(Enum):
    NOT_COVERED = "NOT_COVERED"
    SURVIVES = "SURVIVES"
    KILLED = "KILLED"


class KillReason(Enum):
    FAIL = "FAIL"
    TIME = "TIME"
    EXC = "EXC"
    LIVE = "LIVE"
    UNCOV = "UNCOV"
    NONE = "NONE"


@dataclass(frozen=True)
class TestId:
    class_name: str
    method: str

    @property
    def d4j(self) -> str:
        return f"{self.class_name}::{self.method}"

    @property
    def major(self) -> str:
        return f"{self.class_name}[{self.method}]"


def parse_test_name(name: str) -> TestId:
    name = name.strip()
    # Major: Class[method] or Class[method[param]] (parameterized tests).
    if "[" in name and name.endswith("]"):
        cls, meth = name.split("[", 1)
        meth = meth[:-1]
        if cls and meth:
            return TestId(cls, meth)
    if "::" in name:
        cls, meth = name.split("::", 1)
        return TestId(cls, meth)
    raise ValueError(f"unrecognized test identity: {name!r}")


def load_test_map(path: Path) -> Dict[int, TestId]:
    out: Dict[int, TestId] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if "TestNo" not in (reader.fieldnames or []) or "TestName" not in (reader.fieldnames or []):
            raise ValueError(f"unexpected testMap header: {reader.fieldnames}")
        for row in reader:
            tid = int(row["TestNo"])
            if tid in out:
                raise ValueError(f"duplicate TestNo {tid}")
            out[tid] = parse_test_name(row["TestName"])
    return out


def load_mutants_log(path: Path) -> Dict[int, str]:
    """mutant_id -> raw mutants.log line (identity check)."""
    out: Dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        mid_s, rest = line.split(":", 1)
        mid = int(mid_s)
        if mid in out:
            raise ValueError(f"duplicate mutant id {mid}")
        out[mid] = rest
    return out


def load_pairs(path: Path, left: str, right: str) -> Iterable[Tuple[int, int, Optional[str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        # killMap header: TestNo,MutantNo,[FAIL | TIME | EXC]
        if header[0] != left:
            raise ValueError(f"{path} expected {left} in col0, got {header}")
        extra = header[2] if len(header) > 2 else None
        for row in reader:
            if not row:
                continue
            status = row[2] if len(row) > 2 else None
            yield int(row[0]), int(row[1]), status


def route_a_cells(
    cov_path: Path,
    kill_path: Path,
    n_mutants: int,
    test_ids: Iterable[int],
) -> Dict[Tuple[int, int], Tuple[Cell, KillReason]]:
    """Sparse Major maps → complete (test, mutant) cells."""
    covered = set()
    for t, m, _ in load_pairs(cov_path, "TestNo", "MutantNo"):
        covered.add((t, m))
    killed: Dict[Tuple[int, int], KillReason] = {}
    with kill_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[0] != "TestNo" or header[1] != "MutantNo":
            raise ValueError(f"unexpected killMap header {header}")
        for row in reader:
            key = (int(row[0]), int(row[1]))
            reason = KillReason[row[2]]
            if key in killed:
                raise ValueError(f"duplicate killMap row {key}")
            killed[key] = reason
    cells = {}
    tests = list(test_ids)
    for t in tests:
        for m in range(1, n_mutants + 1):
            key = (t, m)
            if key in killed:
                cells[key] = (Cell.KILLED, killed[key])
            elif key in covered:
                cells[key] = (Cell.SURVIVES, KillReason.LIVE)
            else:
                cells[key] = (Cell.NOT_COVERED, KillReason.UNCOV)
    extra_kills = set(killed) - set(cells)
    if extra_kills:
        raise ValueError(f"killMap keys not in test×mutant grid: {len(extra_kills)}")
    return cells


def route_b_cells_from_kill_csv(path: Path) -> Dict[int, Tuple[Cell, KillReason]]:
    """One Route B kill.csv (single test) → mutant_id -> cell."""
    out: Dict[int, Tuple[Cell, KillReason]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[0] != "MutantNo":
            raise ValueError(f"unexpected kill.csv header {header}")
        for row in reader:
            mid = int(row[0])
            status = KillReason[row[1]]
            if mid in out:
                raise ValueError(f"duplicate mutant {mid} in {path}")
            if status in (KillReason.FAIL, KillReason.TIME, KillReason.EXC):
                out[mid] = (Cell.KILLED, status)
            elif status is KillReason.LIVE:
                out[mid] = (Cell.SURVIVES, status)
            elif status is KillReason.UNCOV:
                out[mid] = (Cell.NOT_COVERED, status)
            else:
                raise ValueError(status)
    return out


def compare_ab(
    a: Dict[Tuple[int, int], Tuple[Cell, KillReason]],
    b: Dict[Tuple[TestId, int], Tuple[Cell, KillReason]],
    test_map: Dict[int, TestId],
) -> dict:
    """Exact discrepancy counts. Timeout reason differences are counted separately."""
    inv = {v: k for k, v in test_map.items()}
    missing_in_b = 0
    missing_in_a = 0
    cell_mismatch = 0
    reason_mismatch_same_cell = 0
    timeout_reason_only = 0
    identical = 0
    details = []
    for (tno, mid), (cell_a, reason_a) in a.items():
        tid = test_map[tno]
        key = (tid, mid)
        if key not in b:
            missing_in_b += 1
            details.append(("missing_in_b", tid.d4j, mid, cell_a.value, None))
            continue
        cell_b, reason_b = b[key]
        if cell_a == cell_b and reason_a == reason_b:
            identical += 1
            continue
        if cell_a == cell_b:
            reason_mismatch_same_cell += 1
            if {reason_a, reason_b} <= {KillReason.FAIL, KillReason.TIME, KillReason.EXC}:
                timeout_reason_only += 1
            details.append(("reason", tid.d4j, mid, reason_a.value, reason_b.value))
        else:
            cell_mismatch += 1
            details.append(("cell", tid.d4j, mid, cell_a.value, cell_b.value))
    a_keys = {(test_map[t], m) for t, m in a}
    for key in b:
        if key not in a_keys:
            missing_in_a += 1
    return {
        "n_a": len(a),
        "n_b": len(b),
        "identical": identical,
        "missing_in_b": missing_in_b,
        "missing_in_a": missing_in_a,
        "cell_mismatch": cell_mismatch,
        "reason_mismatch_same_cell": reason_mismatch_same_cell,
        "timeout_or_kill_reason_only": timeout_reason_only,
        "details_head": details[:50],
    }
