from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

from tools import runfiles
from tools.agent_hooks import shell_command_checks

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_EXPUNGE = "bazelisk clean --noshow_progress --ui_event_filters=-info --expunge_async"
_SETUP_LOCAL_DEV = (
    "bazelisk run --noshow_progress --ui_event_filters=-info //tools:setup_local_dev"
)


def _git(directory: Path, *arguments: str):
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required for these tests")
    _ = subprocess.run(
        [
            git,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *arguments,
        ],
        cwd=directory,
        check=True,
        capture_output=True,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _ = (repository / "README.md").write_text(
        "readme\n", encoding="utf-8", newline="\n"
    )
    _git(repository, "add", "README.md")
    _git(repository, "commit", "--quiet", "-m", "Initial commit")
    return repository


def _worktree(repository: Path, name: str, *, built: bool) -> Path:
    worktree = repository / "worktrees" / name
    _git(repository, "worktree", "add", "--quiet", "--detach", str(worktree))
    if built:
        (worktree / "bazel-out").symlink_to(repository / "nowhere")
    return worktree


def _install_fake_bazelisk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, exit_code: int = 0
) -> Path:
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    run_log = tmp_path / "runs"
    _ = run_log.write_text("", encoding="utf-8", newline="\n")
    bazelisk = bin_directory / "bazelisk"
    script_lines = [
        "#!/bin/sh",
        f"echo \"bazelisk $* in $(pwd)\" >> '{run_log}'",
        "echo 'bazelisk failed'",
        f'[ {exit_code} = 0 ] && case "$*" in',
        # The real setup_local_dev records its successful runs this way.
        '  *setup_local_dev) touch "$(git rev-parse --git-path setup-local-dev-stamp)" ;;',
        "esac",
        f"exit {exit_code}",
    ]
    _ = bazelisk.write_text(
        "\n".join(script_lines) + "\n", encoding="utf-8", newline="\n"
    )
    bazelisk.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_directory}:/usr/bin:/bin")
    return run_log


def _run_hook(monkeypatch: pytest.MonkeyPatch, cwd: Path, command: str) -> str:
    hook_input = {"cwd": str(cwd), "tool_input": {"command": command}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    printed = io.StringIO()
    monkeypatch.setattr("sys.stdout", printed)
    shell_command_checks.main()
    return printed.getvalue()


def test_unrelated_command_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _ = _worktree(repository, "a", built=True)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert (
        _run_hook(
            monkeypatch,
            repository,
            "FOO=1; git status; git worktree remove --force; rm -rf worktrees/a",
        )
        == ""
    )
    assert run_log.read_text(encoding="utf-8").splitlines() == []


def test_git_worktree_remove_expunges_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    worktree = _worktree(repository, "a", built=True)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert (
        _run_hook(monkeypatch, repository, "git worktree remove --force worktrees/a")
        == ""
    )
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_EXPUNGE} in {worktree}"
    ]


def test_git_options_before_the_subcommand_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    worktree = _worktree(repository, "a", built=True)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert (
        _run_hook(monkeypatch, repository, "git --no-pager worktree remove worktrees/a")
        == ""
    )
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_EXPUNGE} in {worktree}"
    ]


def test_each_removed_worktree_is_expunged_once_after_an_earlier_cd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    first = _worktree(repository, "a", built=True)
    second = _worktree(repository, "b", built=True)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert (
        _run_hook(
            monkeypatch,
            tmp_path,
            "cd repository && git worktree remove worktrees/a 2>&1; git worktree remove worktrees/b; git worktree remove worktrees/a",
        )
        == ""
    )
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_EXPUNGE} in {first}",
        f"{_EXPUNGE} in {second}",
    ]


def test_worktree_that_bazel_never_built_in_is_not_expunged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _ = _worktree(repository, "a", built=False)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert _run_hook(monkeypatch, repository, "git worktree remove worktrees/a") == ""
    assert run_log.read_text(encoding="utf-8").splitlines() == []


def test_failed_expunge_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = _repository(tmp_path)
    worktree = _worktree(repository, "a", built=True)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch, exit_code=1)

    assert _run_hook(monkeypatch, repository, "git worktree remove worktrees/a") == ""
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_EXPUNGE} in {worktree}"
    ]


def _project(tmp_path: Path) -> Path:
    repository = _repository(tmp_path)
    for path in (
        "defcl/python/grammar.lark",
        "define/config/project/config.proto",
    ):
        (repository / path).parent.mkdir(parents=True, exist_ok=True)
        _ = (repository / path).write_text("\n", encoding="utf-8", newline="\n")
        _git(repository, "add", path)
    _git(repository, "commit", "--quiet", "-m", "Add project files")
    return repository


def test_first_uv_run_runs_setup_local_dev_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _project(tmp_path)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)
    _ = _run_hook(
        monkeypatch, repository / "define", "FOO=1 BAR=2 uv run --python 3.12 x.py"
    )

    assert _run_hook(monkeypatch, repository, "uv run pytest && uv run x.py") == ""
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_SETUP_LOCAL_DEV} in {repository}"
    ]


def test_changed_source_makes_uv_run_refresh_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _project(tmp_path)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)
    _ = _run_hook(monkeypatch, repository, "uv run x.py")
    stamp = (repository / ".git/setup-local-dev-stamp").stat()
    # Setting the time explicitly keeps coarse filesystem timestamps from
    # making the edit look as old as the stamp.
    os.utime(
        repository / "defcl/python/grammar.lark",
        ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000),
    )

    assert _run_hook(monkeypatch, repository, "uv run x.py") == ""
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_SETUP_LOCAL_DEV} in {repository}",
        f"{_SETUP_LOCAL_DEV} in {repository}",
    ]


def test_failed_setup_local_dev_output_goes_to_the_agent_at_each_uv_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _project(tmp_path)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch, exit_code=1)
    _ = _run_hook(monkeypatch, repository, "uv run x.py")

    assert json.loads(_run_hook(monkeypatch, repository, "uv run x.py")) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"`{_SETUP_LOCAL_DEV}` failed in {repository} before this command"
                + " ran. Its output:\nbazelisk failed\n"
            ),
        }
    }
    assert run_log.read_text(encoding="utf-8").splitlines() == [
        f"{_SETUP_LOCAL_DEV} in {repository}",
        f"{_SETUP_LOCAL_DEV} in {repository}",
    ]


def test_other_uv_subcommands_do_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _project(tmp_path)
    run_log = _install_fake_bazelisk(tmp_path, monkeypatch)

    assert _run_hook(monkeypatch, repository, "uv sync && uv --version") == ""
    assert run_log.read_text(encoding="utf-8").splitlines() == []


def test_prefilter_runs_the_checks_only_for_commands_that_mention_them(
    tmp_path: Path,
):
    _ = shutil.copy(runfiles.resolve_from_env("PREFILTER"), tmp_path)
    _ = (tmp_path / "shell_command_checks.py").write_text(
        "print('checked')\n", encoding="utf-8", newline="\n"
    )
    bash = shutil.which("bash")
    assert bash is not None
    commands = [
        "uv run pytest",
        "git -C /repo worktree remove a",
        "rm -rf build",
        "ls -la",
        "uv sync",
        "git status",
    ]
    checked: dict[str, bool] = {}
    for command in commands:
        result = subprocess.run(
            [bash, str(tmp_path / "shell_command_checks.sh")],
            input=json.dumps({"tool_input": {"command": command}}),
            check=True,
            capture_output=True,
            text=True,
        )
        checked[command] = result.stdout == "checked\n"

    assert checked == {
        "uv run pytest": True,
        "git -C /repo worktree remove a": True,
        "rm -rf build": False,
        "ls -la": False,
        "uv sync": False,
        "git status": False,
    }
