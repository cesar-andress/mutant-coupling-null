#!/usr/bin/env bash
# Clone and initialize the pinned Defects4J release. Does not vendor the clone
# into Git. Does not enable exportKillMap.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../env/pin.env
source "${PIN_ENV:-$SCRIPT_DIR/../env/pin.env}"

DEST="${1:-${D4J_HOME:-/opt/defects4j}}"

if [ -d "$DEST/.git" ]; then
  actual="$(git -C "$DEST" rev-parse HEAD)"
  if [ "$actual" != "$DEFECTS4J_SHA" ]; then
    echo "error: existing checkout SHA $actual != pinned $DEFECTS4J_SHA" >&2
    exit 1
  fi
else
  mkdir -p "$(dirname "$DEST")"
  git clone --branch "$DEFECTS4J_TAG" --depth 1 "$DEFECTS4J_UPSTREAM" "$DEST"
  actual="$(git -C "$DEST" rev-parse HEAD)"
  if [ "$actual" != "$DEFECTS4J_SHA" ]; then
    echo "error: cloned SHA $actual != pinned $DEFECTS4J_SHA" >&2
    exit 1
  fi
fi

cd "$DEST"
cpanm --notest --installdeps .
./init.sh

if [ ! -x "$DEST/major/bin/major" ]; then
  echo "error: Major wrapper missing after init.sh" >&2
  exit 1
fi

echo "Defects4J ready at $DEST"
echo "tag=$DEFECTS4J_TAG sha=$(git -C "$DEST" rev-parse HEAD)"
echo "Major zip identity: major-${MAJOR_VERSION}_jre11 (from init.sh)"
