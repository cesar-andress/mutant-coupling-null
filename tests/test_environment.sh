#!/usr/bin/env bash
# Lightweight environment checks. No scientific interpretation.
set -euo pipefail

# shellcheck source=/dev/null
source "${PIN_ENV:-/opt/artifact/env/pin.env}"

fail=0
check() {
  local label="$1"
  shift
  if "$@"; then
    echo "OK  $label"
  else
    echo "FAIL $label" >&2
    fail=1
  fi
}

java_out="$(java -version 2>&1 || true)"
if printf '%s\n' "$java_out" | grep -Eq 'version "11'; then
  echo "OK  java-major-11"
else
  echo "FAIL java-major-11" >&2
  fail=1
fi
check "java-home-exists" test -x "${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}/bin/java"
check "defects4j-on-path" command -v defects4j
check "d4j-home" test -x "${D4J_HOME:-/opt/defects4j}/framework/bin/defects4j"

actual_sha="$(git -C "${D4J_HOME:-/opt/defects4j}" rev-parse HEAD)"
check "defects4j-sha" test "$actual_sha" = "$DEFECTS4J_SHA"

tag="$(git -C "${D4J_HOME:-/opt/defects4j}" describe --tags --exact-match 2>/dev/null || true)"
check "defects4j-tag" test "$tag" = "$DEFECTS4J_TAG"

check "major-wrapper" test -x "${D4J_HOME:-/opt/defects4j}/major/bin/major"
check "lang-1-active" grep -q '^1,' "${D4J_HOME:-/opt/defects4j}/framework/projects/Lang/active-bugs.csv"
check "lang-1-triggers" test -s "${D4J_HOME:-/opt/defects4j}/framework/projects/Lang/trigger_tests/1"
check "lang-1-modified" test -s "${D4J_HOME:-/opt/defects4j}/framework/projects/Lang/modified_classes/1.src"
check "stock-build-xml-no-exportKillMap" \
  bash -c "! grep -q exportKillMap '${D4J_HOME:-/opt/defects4j}/framework/projects/defects4j.build.xml'"

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "environment checks passed"
