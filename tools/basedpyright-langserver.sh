#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
# stdout is reserved for the LSP protocol, so redirect build output to stderr.
uv run tools/setup_local_dev.py >&2
bazelisk build --noshow_progress //:basedpyright-langserver >&2
export BAZEL_BINDIR=.
exec bazel-bin/basedpyright-langserver_/basedpyright-langserver "$@"
