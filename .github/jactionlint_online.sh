#!/usr/bin/env bash
set -euo pipefail

JACTIONLINT_BIN="$(realpath "$1")"
SHELLCHECK_BIN="$(realpath "$2")"
RUFF_BIN="$(realpath "$3")"

# Without file arguments jactionlint checks the whole repository, which it
# needs before it reports an entry of "ignores:" as unused.
cd "$BUILD_WORKSPACE_DIRECTORY"
exec "$JACTIONLINT_BIN" \
  --no-color \
  --online=strict \
  --strict-exit \
  "--shellcheck=$SHELLCHECK_BIN" \
  "--ruff=$RUFF_BIN"
