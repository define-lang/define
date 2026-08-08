#!/usr/bin/env bash
set -euo pipefail

#!/bin/bash
UV_BIN="$1"

# Bazel places external repositories beside the main runfiles tree, while uv
# resolves local sources relative to pyproject.toml in the main tree.
if [[ ! -d vendored/re2/python ]]; then
  mkdir -p vendored/re2
  cp -LR "$(dirname "$2")" vendored/re2/python
fi

if ! "$UV_BIN" lock --locked; then
  echo "ERROR: uv.lock is out of sync with pyproject.toml!"
  echo "Please run 'bazel run //:update_lock' to fix this."
  exit 1
fi
