from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import (
    bazel,
    build_events,
    coverage,
    mutant,
    results,
    worker,
)

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
        server_failed=lambda _error: None,
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


# Stands in for bazelisk. Each `test` command runs the next of the numbered
# behaviors in the `tests` directory: "fail" exits as a crashed server does,
# "hang" waits until it is killed, and any other passes.
_FAKE_BAZELISK = """\
#!/bin/sh
fake=$(dirname "$0")
for argument; do
  case $argument in
    --build_event_json_file=*) : > "${argument#*=}" ;;
  esac
done
for argument; do
  case $argument in
    -*) ;;
    *) command=$argument; break ;;
  esac
done
case $command in
  info) echo "$fake/output_base" ;;
  build)
    mkdir -p bazel-bin/tools/format/format_
    printf '#!/bin/sh\\n' > bazel-bin/tools/format/format_/format
    chmod +x bazel-bin/tools/format/format_/format ;;
  test)
    count=$(($(cat "$fake/count" 2>/dev/null || echo 0) + 1))
    echo "$count" > "$fake/count"
    behavior=$(cat "$fake/tests/$count" 2>/dev/null)
    case $behavior in
      fail) echo "bazel crashed" >&2; exit 37 ;;
      hang)
        mkdir -p "$fake/output_base/server"
        echo $$ > "$fake/output_base/server/server.pid.txt"
        mkfifo "$fake/never_written"
        exec cat "$fake/never_written" ;;
    esac ;;
esac
"""

_ALL_TESTS = coverage.Selection(skipped=frozenset(), covering_tests=None)

_MUTANT = mutant.Mutant(
    name="lib.rs:1:1: mutate",
    path="lib.rs",
    patch="--- a/lib.rs\n+++ b/lib.rs\n@@ -1 +1 @@\n-original\n+mutated\n",
    lines=(1, 1),
)


def _prepared_worker(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    behaviors: list[str],
    failures: list[worker.ServerFailedError],
    test_timeout: int = 60,
) -> worker.Worker:
    fake = tmp_path / "fake"
    (fake / "tests").mkdir(parents=True)
    for number, behavior in enumerate(behaviors, start=1):
        _ = (fake / "tests" / str(number)).write_text(
            behavior, encoding="utf-8", newline="\n"
        )
    bazelisk = fake / "bazelisk"
    _ = bazelisk.write_text(_FAKE_BAZELISK, encoding="utf-8", newline="\n")
    bazelisk.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ['PATH']}")
    repository = tmp_path / "repository"
    repository.mkdir()
    _ = (repository / ".gitignore").write_text(
        "/bazel-*\n", encoding="utf-8", newline="\n"
    )
    _ = _repository(repository)
    _git(repository, "checkout", "--", "lib.rs")
    _git(repository, "add", ".gitignore")
    _git(
        repository,
        "-c",
        "user.name=Tester",
        "-c",
        "user.email=tester@example.com",
        "commit",
        "--quiet",
        "--message=Ignore Bazel's links",
    )
    work = worker.Worker(
        repository=repository,
        run=results.Run(
            commit="HEAD", area=["//..."], test_timeout=test_timeout, lint_flags=[]
        ),
        index=0,
        testing=lambda _mutated: None,
        server_failed=failures.append,
    )
    work.prepare()
    return work


_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="The fake bazelisk is a shell script."
)


@_POSIX_ONLY
def test_a_crashed_server_tests_the_mutant_again_on_a_new_server(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    failures: list[worker.ServerFailedError] = []
    work = _prepared_worker(tmp_path, monkeypatch, ["", "fail", "pass"], failures)
    work.test_baseline()

    result = work.test(_MUTANT, _ALL_TESTS)

    assert result.outcome == results.Outcome.SURVIVED
    assert [str(failure) for failure in failures] == [
        "Bazel exited with 37\nbazel crashed\n"
    ]


@_POSIX_ONLY
def test_a_server_that_fails_twice_stops_the_worker(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    failures: list[worker.ServerFailedError] = []
    work = _prepared_worker(tmp_path, monkeypatch, ["", "fail", "fail"], failures)
    work.test_baseline()

    with pytest.raises(worker.ServerFailedError):
        _ = work.test(_MUTANT, _ALL_TESTS)

    assert len(failures) == 1
    assert (work.worktree / "lib.rs").read_text(encoding="utf-8") == "original\n"


@_POSIX_ONLY
def test_a_stuck_server_is_killed_and_the_mutant_tested_again(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(worker, "_SLOWEST_ACTION_SECONDS", 1)
    monkeypatch.setattr(worker, "_PROGRESS_CHECK_SECONDS", 0.1)
    failures: list[worker.ServerFailedError] = []
    work = _prepared_worker(
        tmp_path, monkeypatch, ["", "hang", "pass"], failures, test_timeout=0
    )
    work.test_baseline()

    result = work.test(_MUTANT, _ALL_TESTS)

    assert result.outcome == results.Outcome.SURVIVED
    assert [str(failure) for failure in failures] == [
        "Bazel wrote no build events for 1 seconds"
    ]
