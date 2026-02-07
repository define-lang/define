#!/bin/bash
set -euo pipefail

TARGETS=$(bazel query "attr('tags', 'pyright', rdeps(//..., set($@)))")
bazel test $TARGETS