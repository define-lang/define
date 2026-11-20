from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import bazel, build_events, results, worker

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable


def _git(directory: pathlib.Path, *arguments: str):
    _ = subprocess.run(
        [bazel.executable("git"), *arguments],
        cwd=directory,
        capture_output=True,
        check=True,
    )


def _repository(directory: pathlib.Path) -> pathlib.Path:
    source = directory / "lib.rs"
    _ = source.write_text("original\n", encoding="utf-8", newline="\n")
    _git(directory, "init", "--quiet")
    _git(directory, "add", "lib.rs")
    _git(
        directory,
        "-c",
        "user.name=Tester",
        "-c",
        "user.email=tester@example.com",
        "commit",
        "--quiet",
        "--message=Add lib.rs",
    )
    _ = source.write_text("edited\n", encoding="utf-8", newline="\n")
    return source


def _worker(repository: pathlib.Path) -> worker.Worker:
    return worker.Worker(
        repository=repository,
        run=results.Run(commit="HEAD", area=["//..."], test_timeout=60, lint_flags=[]),
        index=0,
        testing=lambda _mutated: None,
    )


_ACTIONS = [worker.Worker.prepare, worker.Worker.remove]


@pytest.mark.parametrize("action", _ACTIONS)
def test_directory_that_is_not_a_worktree_is_refused(
    tmp_path: pathlib.Path, action: Callable[[worker.Worker], None]
):
    source = _repository(tmp_path)
    directory = tmp_path / ".mutation_testing/worker-0"
    directory.mkdir(parents=True)
    with pytest.raises(worker.NotAWorktreeError):
        action(_worker(tmp_path))
    assert directory.is_dir()
    assert source.read_text(encoding="utf-8") == "edited\n"


@pytest.mark.parametrize("action", _ACTIONS)
def test_symlink_to_the_repository_is_refused(
    tmp_path: pathlib.Path, action: Callable[[worker.Worker], None]
):
    source = _repository(tmp_path)
    link = tmp_path / ".mutation_testing/worker-0"
    link.parent.mkdir()
    link.symlink_to(tmp_path)
    with pytest.raises(worker.NotAWorktreeError):
        action(_worker(tmp_path))
    assert link.is_symlink()
    assert source.read_text(encoding="utf-8") == "edited\n"


def test_worktree_with_changes_is_kept(tmp_path: pathlib.Path):
    _ = _repository(tmp_path)
    worktree = tmp_path / ".mutation_testing/worker-0"
    _git(tmp_path, "worktree", "add", "--detach", str(worktree), "HEAD")
    changed = worktree / "lib.rs"
    _ = changed.write_text("mutated\n", encoding="utf-8", newline="\n")
    with pytest.raises(worker.DirtyWorktreeError):
        _worker(tmp_path).remove()
    assert changed.read_text(encoding="utf-8") == "mutated\n"


def test_removing_a_missing_worktree_deletes_its_build_events(tmp_path: pathlib.Path):
    _ = _repository(tmp_path)
    build_events = tmp_path / ".mutation_testing/worker-0.build_events.json"
    build_events.parent.mkdir()
    _ = build_events.write_text("{}\n", encoding="utf-8", newline="\n")
    _worker(tmp_path).remove()
    assert not build_events.exists()


_OUT_OF_MEMORY_LOG = (
    "Running tests\n"
    "The remote execution service stopped this action because it ran out of"
    " its memory limit of 100 MiB.\n"
)


@pytest.mark.parametrize(
    ("failure", "outcome"),
    [
        (
            build_events.TestFailure(label="//a:a_test", timed_out=False, log=""),
            results.Outcome.KILLED,
        ),
        (
            build_events.TestFailure(label="//a:a_test", timed_out=True, log=""),
            results.Outcome.TIMED_OUT,
        ),
        (
            build_events.TestFailure(
                label="//a:a_test", timed_out=False, log=_OUT_OF_MEMORY_LOG
            ),
            results.Outcome.OUT_OF_MEMORY,
        ),
        (
            build_events.ActionFailure(
                label="//a:a",
                mnemonic="Rustc",
                outputs_missing=False,
                output=_OUT_OF_MEMORY_LOG,
            ),
            results.Outcome.OUT_OF_MEMORY,
        ),
    ],
)
def test_failed_result_tells_which_limit_killed_the_mutant(
    failure: build_events.ActionFailure | build_events.TestFailure,
    outcome: results.Outcome,
):
    assert worker.failed_result("mutant", failure, 1.0).outcome == outcome
