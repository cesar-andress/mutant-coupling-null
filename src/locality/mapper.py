"""Deterministic mutant locality relative to the Defects4J patch."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class Locality(Enum):
    PATCH_LINE = "PATCH_LINE"
    PATCH_METHOD = "PATCH_METHOD"
    MODIFIED_CLASS = "MODIFIED_CLASS"
    ELSEWHERE = "ELSEWHERE"
    UNKNOWN = "UNKNOWN"


METHOD_START = re.compile(
    r"^\s*(?:(?:public|protected|private|static|final|native|synchronized|abstract|default)\s+)*"
    r"(?:[\w.<>,\[\]]+\s+)+(?P<name>[A-Za-z_]\w*)\s*\([^;]*$"
)
CTOR = re.compile(
    r"^\s*(?:(?:public|protected|private)\s+)?(?P<name>[A-Za-z_]\w*)\s*\([^;]*$"
)


@dataclass
class MethodSpan:
    name: str
    start_line: int  # 1-based
    end_line: int  # inclusive


def parse_methods(java_src: str) -> List[MethodSpan]:
    """Brace-based method spans. Deterministic; not a full Java parser."""
    lines = java_src.splitlines()
    spans: List[MethodSpan] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        name = None
        m = METHOD_START.match(line)
        if m and "{" in line or (m and i + 1 < len(lines)):
            # skip class/interface/enum declarations
            if re.search(r"\b(class|interface|enum)\b", line):
                i += 1
                continue
            name = m.group("name")
        else:
            cm = CTOR.match(line)
            if cm and not re.search(r"\b(class|interface|enum|return|new)\b", line):
                # constructor heuristic: name matches simple type after modifiers omitted
                name = cm.group("name")
        if name is None:
            i += 1
            continue
        # find opening brace
        j = i
        while j < len(lines) and "{" not in lines[j]:
            j += 1
            if j - i > 5:
                break
        if j >= len(lines) or "{" not in lines[j]:
            i += 1
            continue
        depth = 0
        k = j
        started = False
        while k < len(lines):
            for ch in lines[k]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
            if started and depth == 0:
                spans.append(MethodSpan(name=name, start_line=i + 1, end_line=k + 1))
                i = k + 1
                break
            k += 1
        else:
            i += 1
    return spans


def method_containing(spans: List[MethodSpan], line: int) -> Optional[str]:
    for s in spans:
        if s.start_line <= line <= s.end_line:
            return s.name
    return None


def parse_unified_diff(diff_text: str) -> Dict[str, Set[int]]:
    """file path -> set of changed new-file line numbers (additions/context anchors)."""
    files: Dict[str, Set[int]] = {}
    cur = None
    new_line = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ b/") or line.startswith("+++ "):
            path = line.split(" ", 1)[1]
            if path.startswith("b/"):
                path = path[2:]
            if path == "/dev/null":
                cur = None
                continue
            cur = path
            files.setdefault(cur, set())
        elif line.startswith("@@") and cur:
            # @@ -a,b +c,d @@
            m = re.search(r"\+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
        elif cur and line.startswith("+") and not line.startswith("+++"):
            files[cur].add(new_line)
            new_line += 1
        elif cur and line.startswith(" "):
            new_line += 1
        elif cur and line.startswith("-") and not line.startswith("---"):
            # deletion: record previous new_line as context (no advance)
            if new_line > 0:
                files[cur].add(new_line)
    return files


def classify_mutant(
    mutated_class: str,
    mutated_line: Optional[int],
    mutated_method: str,
    modified_classes: Set[str],
    patch_lines: Dict[str, Set[int]],
    class_to_file: Dict[str, str],
    method_spans: Dict[str, List[MethodSpan]],
) -> Locality:
    if mutated_class not in modified_classes:
        return Locality.ELSEWHERE
    path = class_to_file.get(mutated_class)
    if path and mutated_line is not None and mutated_line in patch_lines.get(path, set()):
        return Locality.PATCH_LINE
    # method-level: either Major method name matches a patched method, or line in patched method span
    patched_methods: Set[str] = set()
    if path and path in method_spans:
        for ln in patch_lines.get(path, set()):
            mn = method_containing(method_spans[path], ln)
            if mn:
                patched_methods.add(mn)
    if mutated_method:
        # Major may include signature bits
        simple = mutated_method.split("(")[0]
        if simple in patched_methods or mutated_method in patched_methods:
            return Locality.PATCH_METHOD
    if mutated_line is not None and path in method_spans:
        mn = method_containing(method_spans[path], mutated_line)
        if mn and mn in patched_methods:
            return Locality.PATCH_METHOD
    return Locality.MODIFIED_CLASS
