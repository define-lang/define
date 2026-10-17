from __future__ import annotations

import io
import json
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from tools.agent_hooks import turn_end_checks

if TYPE_CHECKING:
    from pathlib import Path

_FORMAT = "bazelisk run --noshow_progress --ui_event_filters=-info //:format"
_DEPS = "uv run tools/check_python_deps.py"
_BUF_PLUGIN = "bazelisk build --noshow_progress --ui_event_filters=-info //defcl/buf"
_BUF_LINT = (
    "bazelisk run --noshow_progress --ui_event_filters=-info"
    " @multitool//tools/buf:cwd -- lint"
)
_REPORT_HEADING = "These turn-end checks failed. Fix them:"


def _git(repository: Path, *arguments: str):
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
        cwd=repository,
        check=True,
        capture_output=True,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _ = (repository / ".gitignore").write_text("ignored.txt\n")
    _ = (repository / "committed.txt").write_text("committed\n")
    _ = (repository / "module.py").write_text("\n")
    _ = (repository / "deleted.py").write_text("\n")
    _git(repository, "add", ".gitignore", "committed.txt", "module.py", "deleted.py")
    _git(repository, "commit", "--quiet", "-m", "Initial commit")
    return repository


def _write(repository: Path, path: str, content: str = "\n"):
    (repository / path).parent.mkdir(parents=True, exist_ok=True)
    _ = (repository / path).write_text(content)


def _install_fake_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_code_by_command: dict[str, str],
) -> Path:
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    run_log = tmp_path / "runs"
    _ = run_log.write_text("")
    for tool in ("bazelisk", "uv"):
        script_lines = [
            "#!/bin/sh",
            f"echo \"{tool} $*\" >> '{run_log}'",
            'case "$*" in',
        ]
        for command, shell_code in shell_code_by_command.items():
            command_tool, arguments = command.split(" ", 1)
            if command_tool == tool:
                script_lines.append(f"  '{arguments}') {shell_code};;")
        script_lines.append("esac")
        script = bin_directory / tool
        _ = script.write_text("\n".join(script_lines) + "\n")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_directory}:/usr/bin:/bin")
    return run_log


def _run_hook(
    monkeypatch: pytest.MonkeyPatch, cwd: Path, *, stop_hook_active: bool = False
) -> str:
    hook_input = {"cwd": str(cwd), "stop_hook_active": stop_hook_active}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    printed = io.StringIO()
    monkeypatch.setattr("sys.stdout", printed)
    turn_end_checks.main()
    return printed.getvalue()


def test_clean_repository_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = _repository(tmp_path)
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == []


def test_ignored_file_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = _repository(tmp_path)
    _write(repository, "ignored.txt")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == []


def test_unrelated_change_only_formats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = _repository(tmp_path)
    _write(repository, "committed.txt", "edited\n")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT]


def test_python_dependencies_are_fixed_before_formatting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "module.py", "import os\n")
    (repository / "deleted.py").unlink()
    _write(repository, "pkg/stub.pyi")
    _write(repository, "pkg/BUILD.bazel")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [
        f"{_DEPS} module.py pkg/BUILD.bazel pkg/stub.pyi",
        _FORMAT,
    ]


def test_deleted_python_file_alone_does_not_fix_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    (repository / "deleted.py").unlink()
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT]


def test_staged_deletion_does_not_fix_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _git(repository, "rm", "--quiet", "deleted.py")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT]


def test_unfixable_python_dependencies_continue_the_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "module.py", "import missing\n")
    run_log = _install_fake_tools(
        tmp_path,
        monkeypatch,
        {
            f"{_DEPS} module.py": "echo 'unresolved import missing'; exit 1",
        },
    )

    assert json.loads(_run_hook(monkeypatch, repository)) == {
        "decision": "block",
        "reason": (
            f"{_REPORT_HEADING}\n\n$ {_DEPS} module.py\nunresolved import missing"
        ),
    }
    assert run_log.read_text().splitlines() == [f"{_DEPS} module.py", _FORMAT]


def test_steps_run_at_the_top_of_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "docs/notes.txt")
    _ = _install_fake_tools(
        tmp_path,
        monkeypatch,
        {_FORMAT: "echo \"ran in $(pwd)\"; echo 'dprint crashed' >&2; exit 1"},
    )

    assert json.loads(_run_hook(monkeypatch, repository / "docs")) == {
        "decision": "block",
        "reason": (
            f"{_REPORT_HEADING}\n\n$ {_FORMAT}\nran in {repository}\ndprint crashed"
        ),
    }


def test_linted_proto_changes_run_buf_lint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "defcl/schema/schema.proto")
    _write(repository, "define/config/config.proto")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT, _BUF_PLUGIN, _BUF_LINT]


def test_buf_lint_errors_continue_the_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "define/config/config.proto")
    run_log = _install_fake_tools(
        tmp_path, monkeypatch, {_BUF_LINT: "echo 'config.proto:1:1: bad'; exit 1"}
    )

    assert json.loads(_run_hook(monkeypatch, repository)) == {
        "decision": "block",
        "reason": f"{_REPORT_HEADING}\n\n$ {_BUF_LINT}\nconfig.proto:1:1: bad",
    }
    assert run_log.read_text().splitlines() == [_FORMAT, _BUF_PLUGIN, _BUF_LINT]


def test_buf_plugin_build_failure_skips_buf_lint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "defcl/schema/schema.proto")
    run_log = _install_fake_tools(
        tmp_path, monkeypatch, {_BUF_PLUGIN: "echo 'compile error'; exit 1"}
    )

    assert json.loads(_run_hook(monkeypatch, repository)) == {
        "decision": "block",
        "reason": f"{_REPORT_HEADING}\n\n$ {_BUF_PLUGIN}\ncompile error",
    }
    assert run_log.read_text().splitlines() == [_FORMAT, _BUF_PLUGIN]


def test_every_failed_step_is_reported_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "module.py", "import missing\n")
    _write(repository, "define/config/config.proto")
    _ = _install_fake_tools(
        tmp_path,
        monkeypatch,
        {
            f"{_DEPS} module.py": "echo 'unresolved import missing'; exit 1",
            _FORMAT: "echo 'dprint crashed'; exit 1",
            _BUF_LINT: "echo 'bad comment'; exit 1",
        },
    )

    assert json.loads(_run_hook(monkeypatch, repository)) == {
        "decision": "block",
        "reason": (
            f"{_REPORT_HEADING}\n\n"
            f"$ {_DEPS} module.py\nunresolved import missing\n\n"
            f"$ {_FORMAT}\ndprint crashed\n\n"
            f"$ {_BUF_LINT}\nbad comment"
        ),
    }


def test_failure_after_a_continuation_only_tells_the_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "committed.txt", "edited\n")
    _ = _install_fake_tools(
        tmp_path, monkeypatch, {_FORMAT: "echo 'dprint crashed'; exit 1"}
    )

    assert json.loads(_run_hook(monkeypatch, repository, stop_hook_active=True)) == {
        "systemMessage": f"{_REPORT_HEADING}\n\n$ {_FORMAT}\ndprint crashed"
    }


def test_nothing_runs_when_nothing_changed_since_checks_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    (repository / "committed.txt").unlink()
    _write(repository, "notes.txt")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})
    _ = _run_hook(monkeypatch, repository)

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT]


def test_steps_rerun_after_a_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "notes.txt", "notes\n")
    run_log = _install_fake_tools(tmp_path, monkeypatch, {})
    _ = _run_hook(monkeypatch, repository)
    _write(repository, "notes.txt", "edited notes\n")

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT, _FORMAT]


def test_fixes_made_by_the_steps_are_not_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "notes.txt", "notes\n")
    run_log = _install_fake_tools(
        tmp_path,
        monkeypatch,
        {_FORMAT: "echo formatted >> notes.txt; echo new > formatted.txt"},
    )
    _ = _run_hook(monkeypatch, repository)

    assert _run_hook(monkeypatch, repository) == ""
    assert run_log.read_text().splitlines() == [_FORMAT]


def test_failure_is_checked_again_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = _repository(tmp_path)
    _write(repository, "notes.txt")
    run_log = _install_fake_tools(
        tmp_path, monkeypatch, {_FORMAT: "echo 'dprint crashed'; exit 1"}
    )
    _ = _run_hook(monkeypatch, repository)

    assert json.loads(_run_hook(monkeypatch, repository)) == {
        "decision": "block",
        "reason": f"{_REPORT_HEADING}\n\n$ {_FORMAT}\ndprint crashed",
    }
    assert run_log.read_text().splitlines() == [_FORMAT, _FORMAT]


def test_missing_tool_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = _repository(tmp_path)
    _write(repository, "notes.txt")
    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()
    monkeypatch.setenv("PATH", str(empty_directory))

    with pytest.raises(
        FileNotFoundError, match=r"^bazelisk is required by turn-end checks$"
    ):
        _ = _run_hook(monkeypatch, repository)
