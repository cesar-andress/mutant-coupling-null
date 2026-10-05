"""Locality mapper unit tests (synthetic Java + diffs)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from locality.mapper import (  # noqa: E402
    Locality,
    classify_mutant,
    method_containing,
    parse_methods,
    parse_unified_diff,
)


def test_parse_methods():
    src = """
public class Foo {
  public int bar(int x) {
    return x + 1;
  }
  public void baz() {
    System.out.println(1);
  }
}
"""
    spans = parse_methods(src)
    names = [s.name for s in spans]
    assert "bar" in names and "baz" in names
    bar = next(s for s in spans if s.name == "bar")
    assert method_containing(spans, bar.start_line + 1) == "bar"


def test_diff_and_classify():
    diff = """
--- a/src/Foo.java
+++ b/src/Foo.java
@@ -1,6 +1,7 @@
 public class Foo {
   public int bar(int x) {
-    return x;
+    return x + 1;
   }
 }
"""
    files = parse_unified_diff(diff)
    assert "src/Foo.java" in files
    spans = {
        "src/Foo.java": parse_methods(
            "public class Foo {\n  public int bar(int x) {\n    return x + 1;\n  }\n}\n"
        )
    }
    loc = classify_mutant(
        "Foo",
        3,
        "bar",
        {"Foo"},
        files,
        {"Foo": "src/Foo.java"},
        spans,
    )
    assert loc in (Locality.PATCH_LINE, Locality.PATCH_METHOD)


if __name__ == "__main__":
    test_parse_methods()
    test_diff_and_classify()
    print("ok")
