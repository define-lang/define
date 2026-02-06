#!/usr/bin/env python3
"""Sync permissions from .claude/settings.json to .cursor/cli.json."""

import argparse
import difflib
import json
import sys
from pathlib import Path


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


def load_claude_settings(base_dir: Path) -> dict:
    """Load Claude settings file."""
    settings_path = base_dir / ".claude" / "settings.json"

    with settings_path.open() as f:
        return json.load(f)


def generate_cursor_config(base_dir: Path) -> dict:
    """Generate Cursor config from Claude settings.

    Returns the config dict that should be written to .cursor/cli.json.
    """
    claude_settings = load_claude_settings(base_dir)

    permissions = claude_settings.get("permissions", {})

    cursor_permissions = {
        "allow": [translate_permission(p) for p in permissions.get("allow", [])],
        "deny": [translate_permission(p) for p in permissions.get("deny", [])],
    }

    return {
        "_comment": "This file is auto-generated from .claude/settings.json. Do not edit manually.",
        "permissions": cursor_permissions,
    }


def sync_permissions(base_dir: Path) -> None:
    """Fully overwrite Cursor permissions from Claude settings.

    This function completely replaces .cursor/cli.json with permissions
    translated from .claude/settings.json, which is the source of truth.
    """
    cursor_config = generate_cursor_config(base_dir)

    cursor_dir = base_dir / ".cursor"
    cursor_dir.mkdir(exist_ok=True)

    cursor_path = cursor_dir / "cli.json"
    with cursor_path.open("w") as f:
        json.dump(cursor_config, f, indent=2)
        f.write("\n")

    print(f"Synced permissions to {cursor_path}")


def check_permissions(base_dir: Path) -> None:
    """Check that cursor config matches expected config."""
    expected_config = generate_cursor_config(base_dir)

    cursor_path = base_dir / ".cursor" / "cli.json"

    if not cursor_path.exists():
        print(f"Error: {cursor_path} does not exist")
        print("Run: uv run tools/sync_cursor_permissions.py")
        sys.exit(1)

    with cursor_path.open() as f:
        actual_config = json.load(f)

    if actual_config != expected_config:
        print(
            f"Error: {cursor_path} does not match expected config from .claude/settings.json"
        )
        actual_lines = json.dumps(actual_config, indent=2).splitlines(keepends=True)
        expected_lines = json.dumps(expected_config, indent=2).splitlines(keepends=True)
        diff = difflib.unified_diff(
            actual_lines,
            expected_lines,
            fromfile=".cursor/cli.json (actual)",
            tofile=".cursor/cli.json (expected)",
        )
        print()
        print("".join(diff))
        print("To fix, run: uv run tools/sync_cursor_permissions.py")
        sys.exit(1)


def main() -> None:
    """Run the sync or check process."""
    parser = argparse.ArgumentParser(
        description="Sync or check Cursor permissions from Claude settings"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that .cursor/cli.json matches expected config without modifying it",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent

    if args.check:
        check_permissions(base_dir)
    else:
        sync_permissions(base_dir)


if __name__ == "__main__":
    main()
