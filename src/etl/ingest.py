"""Ingest Route A Major maps into SCHEMA_V1 tables (sparse, no dense grids)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from killmap.parse import KillReason, load_mutants_log, load_pairs, load_test_map, parse_test_name
from etl.schema import SCHEMA_VERSION


@dataclass
class Provenance:
    schema_version: int
    d4j_version: str
    d4j_sha: str
    major_version: str
    git_commit: Optional[str]
    generated_at: str
    source_hashes: Dict[str, str]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_mutants_log_fields(line: str) -> dict:
    parts = line.split(":")
    operator = parts[0] if parts else ""
    mutated_class = ""
    mutated_method = ""
    mutated_line = None
    for i, p in enumerate(parts):
        if "." in p and not p.startswith("<") and mutated_class == "":
            mutated_class = p.split("@")[0]
            if "@" in p:
                mutated_method = p.split("@", 1)[1]
            if i + 1 < len(parts) and parts[i + 1].isdigit():
                mutated_line = int(parts[i + 1])
            break
    return {
        "operator": operator,
        "mutated_file": "",
        "mutated_class": mutated_class,
        "mutated_method": mutated_method,
        "mutated_line": mutated_line,
    }


def ingest_bug(
    project: str,
    bug_id: str,
    a_dir: Path,
    trigger_file: Path,
    d4j_version: str,
    d4j_sha: str,
    major_version: str,
    git_commit: Optional[str] = None,
    commit_db_row: Optional[str] = None,
) -> Tuple[dict, List[dict], List[dict], List[dict], Provenance]:
    tmap = load_test_map(a_dir / "testMap.csv")
    mutants = load_mutants_log(a_dir / "mutants.log")

    covered: Dict[int, Set[int]] = {n: set() for n in tmap}
    for t, m, _ in load_pairs(a_dir / "covMap.csv", "TestNo", "MutantNo"):
        if t in covered:
            covered[t].add(m)
    killed: Dict[int, Dict[int, str]] = {n: {} for n in tmap}
    for t, m, status in load_pairs(a_dir / "killMap.csv", "TestNo", "MutantNo"):
        if t in killed and status:
            killed[t][m] = status

    triggers = set()
    for line in trigger_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- "):
            triggers.add(parse_test_name(line[4:].strip()))

    fixed_commit = buggy_commit = ""
    if commit_db_row:
        parts = commit_db_row.strip().split(",")
        if len(parts) >= 3:
            buggy_commit, fixed_commit = parts[1], parts[2]

    bugs = {
        "project": project,
        "bug_id": bug_id,
        "fixed_commit": fixed_commit,
        "buggy_commit": buggy_commit,
        "d4j_version": d4j_version,
        "d4j_sha": d4j_sha,
        "n_trigger": sum(1 for tid in tmap.values() if tid in triggers),
        "patch_files": "",
        "eligible": True,
        "exclusion_reason": None,
    }

    nontrigger_nos = [n for n, tid in tmap.items() if tid not in triggers]

    tests = []
    seen_test_ids = set()
    for tno, tid in tmap.items():
        cov = covered[tno]
        others = [n for n in nontrigger_nos if n != tno]
        base_excl: Set[int] = set()
        for o in others:
            base_excl |= covered[o]
        if tid.d4j in seen_test_ids:
            raise ValueError(f"canonical test_id collision {tid.d4j}")
        seen_test_ids.add(tid.d4j)
        tests.append(
            {
                "project": project,
                "bug_id": bug_id,
                "test_id": tid.d4j,
                "test_class": tid.class_name,
                "test_method": tid.method,
                "test_decoration": tid.decoration,
                "test_id_raw": tid.raw,
                "is_trigger": tid in triggers,
                "stable": True,
                "n_mutants_covered": len(cov),
                "coverage_gain_if_added": bool(cov - base_excl),
                "trigger_provenance": None,
                "timestamp_relation": None,
                "test_added_date": None,
            }
        )

    mut_rows = []
    for mid, rest in mutants.items():
        fields = parse_mutants_log_fields(rest)
        mut_rows.append(
            {
                "project": project,
                "bug_id": bug_id,
                "mutant_id": mid,
                **fields,
                "is_in_patch_line": None,
                "is_in_patch_method": None,
                "is_in_patch_class": None,
            }
        )

    cell_rows = []
    for tno, tid in tmap.items():
        for mid in covered[tno]:
            if mid in killed[tno]:
                cell_rows.append(
                    {
                        "project": project,
                        "bug_id": bug_id,
                        "test_id": tid.d4j,
                        "mutant_id": mid,
                        "test_covers_mutant": True,
                        "test_kills_mutant": True,
                        "kill_reason": killed[tno][mid],
                    }
                )
            else:
                cell_rows.append(
                    {
                        "project": project,
                        "bug_id": bug_id,
                        "test_id": tid.d4j,
                        "mutant_id": mid,
                        "test_covers_mutant": True,
                        "test_kills_mutant": False,
                        "kill_reason": "LIVE",
                    }
                )

    hashes = {
        "testMap.csv": _sha256(a_dir / "testMap.csv"),
        "covMap.csv": _sha256(a_dir / "covMap.csv"),
        "killMap.csv": _sha256(a_dir / "killMap.csv"),
        "mutants.log": _sha256(a_dir / "mutants.log"),
    }
    prov = Provenance(
        schema_version=SCHEMA_VERSION,
        d4j_version=d4j_version,
        d4j_sha=d4j_sha,
        major_version=major_version,
        git_commit=git_commit,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_hashes=hashes,
    )
    return bugs, tests, mut_rows, cell_rows, prov
