#!/usr/bin/env bash
set -euo pipefail

UV_BIN="$(realpath "$1")"
cd "$BUILD_WORKSPACE_DIRECTORY"
"$UV_BIN" lock
