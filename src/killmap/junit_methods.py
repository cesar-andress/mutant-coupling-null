#!/usr/bin/env python3
"""Extract JUnit test method names from a Java test source file (local, no APIs)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

METHOD = re.compile(
    r"(?:@Test(?:\([^)]*\))?\s+)?public\s+void\s+(?P<name>test\w+|Test\w+)\s*\(",
    re.MULTILINE,
)


def methods_from_java(text: str) -> List[str]:
    names = []
    for m in METHOD.finditer(text):
        name = m.group("name")
        if name not in names:
            names.append(name)
    return names


def methods_from_file(path: Path) -> List[str]:
    return methods_from_java(path.read_text(encoding="utf-8", errors="replace"))
