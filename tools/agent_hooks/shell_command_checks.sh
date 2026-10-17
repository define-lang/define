#!/bin/bash
# Claude Code and Codex run this before every shell command, so it must exit
# quickly. It starts shell_command_checks.py, which decides exactly, only when
# the hook input mentions something that script acts on. Matching too much only
# costs a script run that finds nothing to do.
IFS= read -r -d '' hook_input
case "$hook_input" in
*"uv run"* | *"worktree remove"*)
	exec python3 -I "${BASH_SOURCE[0]%/*}/shell_command_checks.py" <<<"$hook_input"
	;;
esac
