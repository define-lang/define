#!/usr/bin/env python3
"""Sync permissions from .claude/settings.json to Cursor and Codex configs."""

import argparse
import difflib
import json
import shlex
import sys
from pathlib import Path
from typing import cast


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

        if content.endswith(":*"):
            content = content[:-2]

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

    with settings_path.open() as f:
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


def render_codex_pattern(pattern_parts: list[str]) -> str:
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


def append_prefix_rule(
    lines: list[str], pattern_parts: list[str], decision: str
) -> None:
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


def sync_permissions(base_dir: Path) -> None:
    """Fully overwrite agent permissions from Claude settings.

    This function completely replaces .cursor/cli.json and
    .codex/rules/default.rules with permissions translated from
    .claude/settings.json, which is the source of truth.
    """
    permissions = load_permissions(base_dir)
    cursor_config = generate_cursor_config(permissions)
    codex_rules = generate_codex_rules(permissions)

    cursor_dir = base_dir / ".cursor"
    cursor_dir.mkdir(exist_ok=True)

    cursor_path = cursor_dir / "cli.json"
    with cursor_path.open("w") as f:
        json.dump(cursor_config, f, indent=2)
        _ = f.write("\n")

    codex_rules_dir = base_dir / ".codex" / "rules"
    codex_rules_dir.mkdir(parents=True, exist_ok=True)
    codex_path = codex_rules_dir / "default.rules"
    with codex_path.open("w") as f:
        _ = f.write(codex_rules)

    print(f"Synced permissions to {cursor_path}")
    print(f"Synced permissions to {codex_path}")


def report_text_diff(
    actual_content: str,
    expected_content: str,
    actual_label: str,
    expected_label: str,
) -> None:
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


def check_permissions(base_dir: Path) -> None:
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
        with cursor_path.open() as f:
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

    with codex_path.open() as f:
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


def main() -> None:
    """Run the sync or check process."""
    parser = argparse.ArgumentParser(
        description="Sync or check Cursor and Codex permissions from Claude settings"
    )
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Check that .cursor/cli.json and .codex/rules/default.rules match expected config without modifying them",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent

    check = cast("bool", args.check)
    if check:
        check_permissions(base_dir)
    else:
        sync_permissions(base_dir)


if __name__ == "__main__":
    main()
