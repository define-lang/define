from __future__ import annotations

import json
import re
import shutil
import typing

from tools import runfiles, sync_agent_permissions

if typing.TYPE_CHECKING:
    import pathlib

    import pytest

_AGY_RULE_PATTERN = re.compile(
    r"^(command|read_file|write_file|read_url|execute_url|mcp|unsandboxed)\(.*\)$"
)


def _read_json(path: pathlib.Path) -> dict[str, object]:
    return typing.cast(
        "dict[str, object]",
        json.loads(path.read_text(encoding="utf-8")),
    )


def _set_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    return fake_home


def _write_claude_settings(base_dir: pathlib.Path, permissions: dict[str, list[str]]):
    claude_dir = base_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    _ = (claude_dir / "settings.json").write_text(
        json.dumps({"permissions": permissions}),
        encoding="utf-8",
        newline="\n",
    )


def test_agent_permissions_match_claude_settings(capsys: pytest.CaptureFixture[str]):
    base_dir = runfiles.resolve_from_env("CLAUDE_SETTINGS").parent.parent
    sync_agent_permissions.check_permissions(base_dir)
    assert capsys.readouterr().out == ""


def test_sync_agy_permissions_from_repo_claude_settings(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    fake_home = _set_home(tmp_path, monkeypatch)
    claude_settings = runfiles.resolve_from_env("CLAUDE_SETTINGS")
    (tmp_path / ".claude").mkdir()
    _ = shutil.copy2(claude_settings, tmp_path / ".claude" / "settings.json")

    sync_agent_permissions.sync_permissions(
        tmp_path, agy_project=sync_agent_permissions.DEFAULT_AGY_PROJECT
    )

    project_path = (
        fake_home / ".gemini" / "config" / "projects" / "default-cli-project.json"
    )
    saved = _read_json(project_path)
    assert saved["id"] == "default-cli-project"
    assert saved["name"] == "CLI Project"
    outer_grants = typing.cast("dict[str, object]", saved["permissionGrants"])
    inner_grants = typing.cast("dict[str, list[str]]", outer_grants["permissionGrants"])
    assert set(inner_grants) == {"allow", "deny"}
    assert (
        f"read_file({(fake_home / '.cache' / 'bazel').as_posix()})"
        in inner_grants["allow"]
    )
    assert "read_url(registry.bazel.build)" in inner_grants["allow"]
    assert "command(bazelisk)" in inner_grants["allow"]
    assert "command(source .venv/bin/activate)" in inner_grants["allow"]
    assert "command(regex:find .* -exec cat)" in inner_grants["allow"]
    assert "command(regex:gh api repos/.*/releases)" in inner_grants["allow"]
    assert "command(regex:gh api repos/.*/contents/.*)" in inner_grants["allow"]
    assert "command(pip)" in inner_grants["deny"]
    assert "command(uv run python -m pip)" in inner_grants["deny"]

    for rules in inner_grants.values():
        assert len(rules) == len(set(rules))
        for rule in rules:
            assert _AGY_RULE_PATTERN.match(rule)


def test_sync_permissions_skips_agy_by_default(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    fake_home = _set_home(tmp_path, monkeypatch)
    _write_claude_settings(tmp_path, {"allow": ["Bash(bazelisk *)"]})

    projects_dir = fake_home / ".gemini" / "config" / "projects"
    projects_dir.mkdir(parents=True)
    default_project = projects_dir / "default-cli-project.json"
    initial_content = json.dumps(
        {
            "id": "default-cli-project",
            "name": "CLI Project",
            "projectResources": {},
            "permissionGrants": {"permissionGrants": {}},
        }
    )
    _ = default_project.write_text(initial_content, encoding="utf-8", newline="\n")

    sync_agent_permissions.sync_permissions(tmp_path)
    assert default_project.read_text(encoding="utf-8") == initial_content


def test_sync_agy_permissions_merges_existing_project(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    fake_home = _set_home(tmp_path, monkeypatch)
    _write_claude_settings(
        tmp_path,
        {
            "allow": [
                "Bash(bazelisk *)",
                "Bash(git status)",
                "Bash(git status *)",
            ],
            "deny": ["Bash(pip *)"],
        },
    )

    projects_dir = fake_home / ".gemini" / "config" / "projects"
    projects_dir.mkdir(parents=True)
    default_project = projects_dir / "default-cli-project.json"
    _ = default_project.write_text(
        json.dumps(
            {
                "id": "default-cli-project",
                "name": "CLI Project",
                "projectResources": {"folders": ["/home/testuser/repo"]},
                "permissionGrants": {
                    "migrated": True,
                    "permissionGrants": {
                        "allow": ["command(bazelisk)", "command(docker)"],
                    },
                },
            }
        ),
        encoding="utf-8",
        newline="\n",
    )

    sync_agent_permissions.sync_permissions(
        tmp_path, agy_project=sync_agent_permissions.DEFAULT_AGY_PROJECT
    )
    assert _read_json(default_project) == {
        "id": "default-cli-project",
        "name": "CLI Project",
        "projectResources": {"folders": ["/home/testuser/repo"]},
        "permissionGrants": {
            "migrated": True,
            "permissionGrants": {
                "allow": [
                    "command(bazelisk)",
                    "command(docker)",
                    "command(git status)",
                ],
                "deny": ["command(pip)"],
            },
        },
    }


def test_sync_agy_permissions_creates_named_project(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    fake_home = _set_home(tmp_path, monkeypatch)
    _write_claude_settings(
        tmp_path,
        {
            "allow": ["Bash(bazelisk *)"],
            "deny": ["Bash(pip *)"],
        },
    )

    sync_agent_permissions.sync_permissions(tmp_path, agy_project="define")
    assert _read_json(
        fake_home / ".gemini" / "config" / "projects" / "define.json"
    ) == {
        "id": "define",
        "name": "define",
        "projectResources": {},
        "permissionGrants": {
            "permissionGrants": {
                "allow": ["command(bazelisk)"],
                "deny": ["command(pip)"],
            },
        },
    }
