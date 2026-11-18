from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import bazel, build_events, results, worker

if TYPE_CHECKING:
    import pathlib

_TEST = "//crates/example:example_test"


def test_failed_action_kills():
    failure = build_events.ActionFailure(
        label="//crates/example:example", mnemonic="Clippy"
    )
    assert worker.outcome(failure) == results.Outcome.KILLED


def test_failed_test_kills():
    failure = build_events.TestFailure(label=_TEST, timed_out=False)
    assert worker.outcome(failure) == results.Outcome.KILLED


def test_timed_out_test():
    failure = build_events.TestFailure(label=_TEST, timed_out=True)
    assert worker.outcome(failure) == results.Outcome.TIMED_OUT


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


def _prepare(repository: pathlib.Path, worktree: pathlib.Path):
    worker.Worker(
        repository=repository,
        worktree=worktree,
        run=results.Run(commit="HEAD", area=["//..."], test_timeout=60),
    ).prepare()


def test_directory_that_is_not_a_worktree_is_refused(tmp_path: pathlib.Path):
    source = _repository(tmp_path)
    directory = tmp_path / ".mutation_testing/worker-0"
    directory.mkdir(parents=True)
    with pytest.raises(worker.NotAWorktreeError):
        _prepare(tmp_path, directory)
    assert source.read_text(encoding="utf-8") == "edited\n"


def test_symlink_to_the_repository_is_refused(tmp_path: pathlib.Path):
    source = _repository(tmp_path)
    link = tmp_path / ".mutation_testing/worker-0"
    link.parent.mkdir()
    link.symlink_to(tmp_path)
    with pytest.raises(worker.NotAWorktreeError):
        _prepare(tmp_path, link)
    assert source.read_text(encoding="utf-8") == "edited\n"
