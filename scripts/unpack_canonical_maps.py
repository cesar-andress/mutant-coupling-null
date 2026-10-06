#!/usr/bin/env python3
"""Unpack the v1.0.0 canonical-map archive into results/raw/t5/."""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("archive")
    p.add_argument("--dest", default="results/raw/t5")
    args = p.parse_args()
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.archive, "r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            # canonical_maps/Project-id/filename
            parts = Path(m.name).parts
            if len(parts) < 3 or parts[0] != "canonical_maps":
                continue
            bugdir = dest / parts[1]
            bugdir.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(m)
            if src is None:
                raise SystemExit(f"cannot extract {m.name}")
            (bugdir / parts[-1]).write_bytes(src.read())
    print("unpacked into", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
