#!/usr/bin/env python3
"""Sync permissions from .claude/settings.json to Cursor, Codex, and Antigravity configs."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

DEFAULT_AGY_PROJECT = "default-cli-project"
_REGEX_SPECIAL_CHARS = re.compile(r"([.+?()\[\]{}^$|\\])")


def translate_permission(permission: str) -> str:
    """Translate Claude permission format to Cursor format.

    Translates:
    - Bash(command:*) -> Shell(command)
    - Read(path) -> Read(path) (pass through)
    - Write(path) -> Write(path) (pass through)
    - Other types pass through unchanged

    Examples:
        Bash(echo:*) -> Shell(echo)
        Bash(git status:*) -> Shell(git status)
        Read(src/**/*.ts) -> Read(src/**/*.ts)
        Write(package.json) -> Write(package.json)
    """
    if permission.startswith("Bash(") and permission.endswith(")"):
        content = permission[5:-1]

        content = content.removesuffix(":*")

        return f"Shell({content})"

    return permission


def extract_bash_command(permission: str) -> str | None:
    """Extract the shell command pattern from a Claude Bash permission."""
    if not permission.startswith("Bash(") or not permission.endswith(")"):
        return None

    content = permission[5:-1]
    if content.endswith(":*"):
        return content[:-2]
    return content


def load_claude_settings(base_dir: Path) -> dict[str, object]:
    """Load Claude settings file."""
    settings_path = base_dir / ".claude" / "settings.json"

    with settings_path.open(encoding="utf-8") as f:
        return cast("dict[str, object]", json.load(f))


def load_permissions(base_dir: Path) -> dict[str, list[str]]:
    """Load permission lists from Claude settings."""
    claude_settings = load_claude_settings(base_dir)
    return cast("dict[str, list[str]]", claude_settings.get("permissions", {}))


def generate_cursor_config(permissions: dict[str, list[str]]) -> dict[str, object]:
    """Generate Cursor config from Claude settings permissions."""
    cursor_permissions = {
        "allow": [translate_permission(p) for p in permissions.get("allow", [])],
        "deny": [translate_permission(p) for p in permissions.get("deny", [])],
    }

    ask_permissions = [translate_permission(p) for p in permissions.get("ask", [])]
    if ask_permissions:
        cursor_permissions["ask"] = ask_permissions

    return {
        "_comment": "This file is auto-generated from .claude/settings.json. Do not edit manually.",
        "permissions": cursor_permissions,
    }


def quote_codex_rule(value: str) -> str:
    """Quote a string value for Codex .rules Starlark format."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_codex_pattern(pattern_parts: Iterable[str]) -> str:
    """Render a Codex pattern list in Starlark syntax."""
    quoted_parts = [quote_codex_rule(part) for part in pattern_parts]
    return f"[{', '.join(quoted_parts)}]"


def _sanitize_pattern_part(part: str) -> str | None:
    """Drop trailing asterisks from a token and skip pure wildcards."""
    if part == "*":
        return None

    stripped = part.rstrip("*")
    if not stripped:
        return None

    return stripped


def command_to_pattern_parts(command: str) -> list[str]:
    """Convert a bash permission command into Codex pattern parts."""
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()

    sanitized_parts: list[str] = []
    for part in parts:
        sanitized = _sanitize_pattern_part(part)
        if sanitized:
            sanitized_parts.append(sanitized)
    return sanitized_parts


def append_prefix_rule(lines: list[str], pattern_parts: list[str], decision: str):
    """Append a single Codex prefix_rule block."""
    lines.extend(
        [
            "prefix_rule(",
            f"    pattern = {render_codex_pattern(pattern_parts)},",
            f"    decision = {quote_codex_rule(decision)},",
            ")",
            "",
        ]
    )


def generate_codex_rules(permissions: dict[str, list[str]]) -> str:
    """Generate Codex rules file from Claude settings permissions."""
    lines = [
        "# This file is auto-generated from .claude/settings.json. Do not edit manually.",
        "",
    ]

    for permission in permissions.get("allow", []):
        command = extract_bash_command(permission)
        if command is not None:
            pattern_parts = command_to_pattern_parts(command)
            if pattern_parts:
                append_prefix_rule(lines, pattern_parts, "allow")

    for permission in permissions.get("ask", []):
        command = extract_bash_command(permission)
        if command is not None:
            pattern_parts = command_to_pattern_parts(command)
            if pattern_parts:
                append_prefix_rule(lines, pattern_parts, "prompt")

    for permission in permissions.get("deny", []):
        command = extract_bash_command(permission)
        if command is not None:
            pattern_parts = command_to_pattern_parts(command)
            if pattern_parts:
                # Codex uses "forbidden" (not "deny") for blocking rules.
                append_prefix_rule(lines, pattern_parts, "forbidden")

    return "\n".join(lines).rstrip() + "\n"


def _agy_project_path(project: str) -> Path:
    return Path.home() / ".gemini" / "config" / "projects" / f"{project}.json"


def _glob_token_to_regex(token: str) -> str:
    return ".*".join(
        _REGEX_SPECIAL_CHARS.sub(r"\\\1", part) for part in token.split("*")
    )


def _translate_agy_bash_command(command: str) -> str:
    tokens = shlex.split(command)
    if tokens[-1] == "*":
        _ = tokens.pop()

    if any("*" in token for token in tokens):
        regex_tokens = [_glob_token_to_regex(token) for token in tokens]
        return f"command(regex:{' '.join(regex_tokens)})"

    return f"command({' '.join(tokens)})"


def _translate_agy_permission(permission: str) -> str | None:
    command = extract_bash_command(permission)
    if command is not None:
        return _translate_agy_bash_command(command)

    if permission.startswith("Read(") and permission.endswith(")"):
        target = permission[5:-1].removesuffix("/**")
        return f"read_file({Path(target).expanduser().as_posix()})"

    if permission.startswith("WebFetch(domain:") and permission.endswith(")"):
        return f"read_url({permission[16:-1]})"

    return None


def _generate_agy_permissions(
    permissions: Mapping[str, Iterable[str]],
) -> dict[str, list[str]]:
    agy_permissions: dict[str, list[str]] = {}
    for category in ("allow", "ask", "deny"):
        translated_rules: list[str] = []
        seen: set[str] = set()
        for permission in permissions.get(category, ()):
            rule = _translate_agy_permission(permission)
            if rule is not None and rule not in seen:
                translated_rules.append(rule)
                seen.add(rule)
        if translated_rules:
            agy_permissions[category] = translated_rules
    return agy_permissions


def _merge_agy_project_config(
    existing_config: Mapping[str, object],
    agy_permissions: Mapping[str, Iterable[str]],
    project_id: str,
) -> dict[str, object]:
    merged = dict(existing_config)
    _ = merged.setdefault("id", project_id)
    default_name = "CLI Project" if project_id == DEFAULT_AGY_PROJECT else project_id
    _ = merged.setdefault("name", default_name)
    _ = merged.setdefault("projectResources", {})

    raw_outer_grants = merged.get("permissionGrants")
    outer_grants = (
        dict(cast("Mapping[str, object]", raw_outer_grants))
        if isinstance(raw_outer_grants, dict)
        else {}
    )
    raw_inner_grants = outer_grants.get("permissionGrants")
    inner_grants = (
        dict(cast("Mapping[str, object]", raw_inner_grants))
        if isinstance(raw_inner_grants, dict)
        else {}
    )

    for category in ("allow", "ask", "deny"):
        raw_existing = inner_grants.get(category)
        existing_rules = (
            list(cast("list[str]", raw_existing))
            if isinstance(raw_existing, list)
            else []
        )
        seen = set(existing_rules)
        for rule in agy_permissions.get(category, ()):
            if rule not in seen:
                existing_rules.append(rule)
                seen.add(rule)
        if existing_rules:
            inner_grants[category] = existing_rules

    outer_grants["permissionGrants"] = inner_grants
    merged["permissionGrants"] = outer_grants
    return merged


def _sync_agy_permissions(permissions: Mapping[str, Iterable[str]], project_path: Path):
    agy_permissions = _generate_agy_permissions(permissions)

    existing_config: dict[str, object] = {}
    if project_path.exists():
        with project_path.open(encoding="utf-8") as f:
            existing_config = cast("dict[str, object]", json.load(f))

    merged_config = _merge_agy_project_config(
        existing_config, agy_permissions, project_path.stem
    )
    project_path.parent.mkdir(parents=True, exist_ok=True)
    with project_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(merged_config, f, indent=2)
        _ = f.write("\n")

    print(f"Synced permissions to {project_path}")


def sync_permissions(base_dir: Path, agy_project: str | None = None):
    """Sync agent permissions from Claude settings.

    Replaces .cursor/cli.json and .codex/rules/default.rules with permissions
    translated from .claude/settings.json. Also merges translated rules into an
    Antigravity project config when agy_project is specified.
    """
    permissions = load_permissions(base_dir)
    cursor_config = generate_cursor_config(permissions)
    codex_rules = generate_codex_rules(permissions)

    cursor_dir = base_dir / ".cursor"
    cursor_dir.mkdir(exist_ok=True)

    cursor_path = cursor_dir / "cli.json"
    with cursor_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(cursor_config, f, indent=2)
        _ = f.write("\n")

    codex_rules_dir = base_dir / ".codex" / "rules"
    codex_rules_dir.mkdir(parents=True, exist_ok=True)
    codex_path = codex_rules_dir / "default.rules"
    with codex_path.open("w", encoding="utf-8", newline="\n") as f:
        _ = f.write(codex_rules)

    print(f"Synced permissions to {cursor_path}")
    print(f"Synced permissions to {codex_path}")

    if agy_project is not None:
        _sync_agy_permissions(permissions, _agy_project_path(agy_project))


def report_text_diff(
    actual_content: str,
    expected_content: str,
    actual_label: str,
    expected_label: str,
):
    """Print a unified diff for two text blobs."""
    actual_lines = actual_content.splitlines(keepends=True)
    expected_lines = expected_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        actual_lines,
        expected_lines,
        fromfile=actual_label,
        tofile=expected_label,
    )
    print()
    print("".join(diff))


def check_permissions(base_dir: Path):
    """Check that Cursor and Codex configs match expected content."""
    permissions = load_permissions(base_dir)
    expected_config = generate_cursor_config(permissions)
    expected_codex_rules = generate_codex_rules(permissions)

    cursor_path = base_dir / ".cursor" / "cli.json"
    codex_path = base_dir / ".codex" / "rules" / "default.rules"
    has_errors = False

    if not cursor_path.exists():
        print(f"Error: {cursor_path} does not exist")
        has_errors = True
    else:
        with cursor_path.open(encoding="utf-8") as f:
            actual_config = cast("dict[str, object]", json.load(f))

        if actual_config != expected_config:
            print(
                f"Error: {cursor_path} does not match expected config from .claude/settings.json"
            )
            report_text_diff(
                json.dumps(actual_config, indent=2),
                json.dumps(expected_config, indent=2),
                ".cursor/cli.json (actual)",
                ".cursor/cli.json (expected)",
            )
            has_errors = True

    with codex_path.open(encoding="utf-8") as f:
        actual_codex_rules = f.read()

    if actual_codex_rules != expected_codex_rules:
        print(
            f"Error: {codex_path} does not match expected config from .claude/settings.json"
        )
        report_text_diff(
            actual_codex_rules,
            expected_codex_rules,
            ".codex/rules/default.rules (actual)",
            ".codex/rules/default.rules (expected)",
        )
        has_errors = True

    if has_errors:
        print("To fix, run: uv run tools/sync_agent_permissions.py")
        sys.exit(1)


def main():
    """Run the sync or check process."""
    parser = argparse.ArgumentParser(
        description="Sync or check Cursor, Codex, and Antigravity permissions from Claude settings"
    )
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Check that .cursor/cli.json and .codex/rules/default.rules match expected config without modifying them",
    )
    _ = parser.add_argument(
        "--agy",
        dest="agy_project",
        nargs="?",
        const=DEFAULT_AGY_PROJECT,
        default=None,
        metavar="PROJECT",
        help=(
            "Also merge permissions into ~/.gemini/config/projects/<project>.json "
            f"(default: {DEFAULT_AGY_PROJECT})"
        ),
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent

    check = cast("bool", args.check)
    agy_project = cast("str | None", args.agy_project)
    if check:
        check_permissions(base_dir)
    else:
        sync_permissions(base_dir, agy_project=agy_project)


if __name__ == "__main__":
    main()
