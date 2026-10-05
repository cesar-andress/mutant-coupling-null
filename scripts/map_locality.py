#!/usr/bin/env python3
"""Map mutant locality for bugs with Route A maps. Uses Defects4J patches + checkout source."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from etl.ingest import parse_mutants_log_fields  # noqa: E402
from killmap.parse import load_mutants_log  # noqa: E402
from locality.mapper import Locality, classify_mutant, parse_methods, parse_unified_diff  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    d4j = Path(sys.argv[2] if len(sys.argv) > 2 else root / "external" / "defects4j")
    raw = root / "results" / "raw" / "t5"
    out_dir = root / "results" / "derived" / "locality"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = root / "results" / "raw" / "t7_checkout"
    work.mkdir(parents=True, exist_ok=True)

    env = {"PATH": f"{d4j}/framework/bin:" + str(Path("/usr/bin")), "TZ": "America/Los_Angeles"}
    # Prefer host PATH with defects4j if D4J_HOME set
    import os

    d4j_home = Path(os.environ.get("D4J_HOME", d4j))
    env["PATH"] = f"{d4j_home}/framework/bin:" + os.environ.get("PATH", "")
    env["TZ"] = "America/Los_Angeles"

    summary = {"bugs": 0, "mutants": 0, "with_method": 0, "counts": {}}
    rows = []
    lang_dirs = sorted(raw.glob("Lang-*"))
    # first 10 for detailed + all for stats if source available
    for d in lang_dirs:
        if not (d / "mutants.log").is_file():
            continue
        bid = d.name.split("-", 1)[1]
        project = "Lang"
        patch = d4j_home / "framework" / "projects" / project / "patches" / f"{bid}.src.patch"
        mod = d4j_home / "framework" / "projects" / project / "modified_classes" / f"{bid}.src"
        if not patch.is_file() or not mod.is_file():
            continue
        modified = {ln.strip() for ln in mod.read_text().splitlines() if ln.strip()}
        patch_lines = parse_unified_diff(patch.read_text(encoding="utf-8", errors="replace"))
        # checkout fixed version once per bug
        w = work / f"{project}-{bid}f"
        if not (w / ".defects4j.config").is_file() and not any(w.iterdir()) if w.exists() else True:
            w.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(
                ["defects4j", "checkout", "-p", project, "-v", f"{bid}f", "-w", str(w)],
                env={**os.environ, **env},
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                continue
        src_rel = subprocess.check_output(
            ["defects4j", "export", "-p", "dir.src.classes", "-w", str(w)],
            env={**os.environ, **env},
            text=True,
        ).strip().splitlines()[-1]
        class_to_file = {}
        method_spans = {}
        for cls in modified:
            rel = Path(*cls.split(".")).with_suffix(".java")
            fpath = w / src_rel / rel
            if fpath.is_file():
                # key patch paths often like src/main/java/...
                # match patch file endings
                class_to_file[cls] = str(fpath.relative_to(w))
                method_spans[str(fpath.relative_to(w))] = parse_methods(
                    fpath.read_text(encoding="utf-8", errors="replace")
                )
        # also index patch paths by suffix match
        path_by_suffix = {}
        for p in patch_lines:
            path_by_suffix[Path(p).name] = p

        mutants = load_mutants_log(d / "mutants.log")
        for mid, rest in mutants.items():
            fields = parse_mutants_log_fields(rest)
            cls = fields["mutated_class"]
            # remap class_to_file path to patch path if needed
            c2f = dict(class_to_file)
            if cls in c2f:
                local = c2f[cls]
                # if patch uses different prefix, find matching patch key
                for pp in patch_lines:
                    if local.endswith(pp) or pp.endswith(Path(local).name) or local.endswith(Path(pp).as_posix()):
                        c2f[cls] = pp
                        if local in method_spans and pp not in method_spans:
                            method_spans[pp] = method_spans[local]
                        break
            loc = classify_mutant(
                cls,
                fields["mutated_line"],
                fields["mutated_method"],
                modified,
                patch_lines,
                c2f,
                method_spans,
            )
            rows.append(
                {
                    "project": project,
                    "bug_id": bid,
                    "mutant_id": mid,
                    "locality": loc.value,
                    "mutated_class": cls,
                    "mutated_line": fields["mutated_line"],
                    "mutated_method": fields["mutated_method"],
                }
            )
            summary["mutants"] += 1
            summary["counts"][loc.value] = summary["counts"].get(loc.value, 0) + 1
            if fields["mutated_method"] or fields["mutated_line"] is not None:
                summary["with_method"] += 1
        summary["bugs"] += 1

    (out_dir / "mutant_locality.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    try:
        import pandas as pd

        pd.DataFrame(rows).to_parquet(out_dir / "mutant_locality.parquet", index=False)
    except Exception:
        pass
    permit = [
        r
        for r in rows
        if r.get("mutated_line") is not None or (r.get("mutated_method") or "") != ""
    ]
    labeled = [r for r in permit if r["locality"] != "UNKNOWN"]
    cov = len(labeled) / len(permit) if permit else 1.0
    modish = [r for r in rows if r["locality"] in ("PATCH_LINE", "PATCH_METHOD", "MODIFIED_CLASS")]
    mapped = [r for r in modish if r["locality"] in ("PATCH_LINE", "PATCH_METHOD")]
    summary["method_level_coverage"] = cov
    summary["patch_method_or_line_rate"] = (len(mapped) / len(modish) if modish else None)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if cov >= 0.95 else 2


if __name__ == "__main__":
    raise SystemExit(main())
