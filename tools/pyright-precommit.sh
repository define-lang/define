#!/bin/bash
set -euo pipefail

sources=()
for filename in "$@"; do
	sources+=("\"$filename\"")
done

query_result=$(bazelisk query "attr('tags', 'pyright', rdeps(//..., set(${sources[*]})))")
query_result=${query_result//$'\r'/}
if [[ -z "$query_result" ]]; then
	exit 0
fi

targets=()
while IFS= read -r target; do
	targets+=("$target")
done <<<"$query_result"
bazelisk test "${targets[@]}"
