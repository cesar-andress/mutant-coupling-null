#!/usr/bin/env python3
"""Pack the 481 canonical kill maps for the v1.0.0 GitHub Release asset."""

from __future__ import annotations

import csv
import hashlib
import tarfile
from pathlib import Path

MAP_FILES = ("testMap.csv", "covMap.csv", "killMap.csv", "mutants.log", "trigger_tests.txt")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fs = root / "results" / "derived" / "full_study"
    raw = root / "results" / "raw" / "t5"
    out_dir = Path("/tmp/mcn-v1-staging")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "docs" / "release" / "CANONICAL_MAP_MANIFEST.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    bugs = list(csv.DictReader((fs / "core_completion" / "bug_level_completion.csv").open()))
    if len(bugs) != 481:
        raise SystemExit(f"expected 481 canonical bugs, got {len(bugs)}")

    rows = []
    archive = out_dir / "mutant-coupling-null-canonical-data-v1.0.0.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for b in bugs:
            project, bid = b["project"], b["bug_id"]
            src = raw / f"{project}-{bid}"
            for name in MAP_FILES:
                p = src / name
                if not p.is_file():
                    raise SystemExit(f"missing {p}")
                rel = f"canonical_maps/{project}-{bid}/{name}"
                tar.add(p, arcname=rel)
                rows.append(
                    {
                        "project": project,
                        "bug_id": bid,
                        "filename": name,
                        "archive_path": rel,
                        "status": "canonical_included",
                        "sha256": sha256(p),
                        "size_bytes": str(p.stat().st_size),
                        "provenance": "Major 3.0.1 kill-map export on Defects4J 3.0.1 fixed revision",
                    }
                )
    fields = ["project", "bug_id", "filename", "archive_path", "status", "sha256", "size_bytes", "provenance"]
    with manifest_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    n_bugs = len({(r["project"], r["bug_id"]) for r in rows})
    print(f"bugs={n_bugs} files={len(rows)} archive={archive} bytes={archive.stat().st_size}")
    print("archive_sha256", sha256(archive))
    print("manifest", manifest_path)
    if n_bugs != 481:
        raise SystemExit("canonical bug count mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
