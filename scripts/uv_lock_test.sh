#!/usr/bin/env bash
set -euo pipefail

#!/bin/bash
UV_BIN="$1"

if ! "$UV_BIN" lock --locked; then
  echo "ERROR: uv.lock is out of sync with pyproject.toml!"
  echo "Please run 'bazel run //:update_lock' to fix this."
  exit 1
fi
