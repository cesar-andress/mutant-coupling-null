#!/usr/bin/env bash
# Apply the minimal Major kill-map patch to a Defects4J tree. Idempotent.
set -euo pipefail
D4J_HOME="${1:-${D4J_HOME:?set D4J_HOME or pass the Defects4J root}}"
PATCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/patches/defects4j-major-killmap.patch"
TARGET="$D4J_HOME/framework/projects/defects4j.build.xml"
if grep -q 'exportKillMap="true"' "$TARGET"; then
  echo "kill-map patch already present in $TARGET"
  exit 0
fi
patch -p1 --directory "$D4J_HOME" < "$PATCH"
if ! grep -q 'exportKillMap="true"' "$TARGET"; then
  echo "error: patch applied but exportKillMap not found" >&2
  exit 1
fi
echo "applied kill-map patch to $D4J_HOME"
