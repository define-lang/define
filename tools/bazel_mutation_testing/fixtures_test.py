"""Run the mutation tester on the fixtures in testdata, whose outcomes are known.

This runs Bazel in a worktree of the workspace, so run it with:
    bazelisk run //tools/bazel_mutation_testing:fixtures_test
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import pathlib
import signal
import subprocess
import tempfile
from typing import IO, TYPE_CHECKING, cast

import msgspec
import pytest

from tools import runfiles
from tools.bazel_mutation_testing import bazel, results

if TYPE_CHECKING:
    from collections.abc import Generator

_WORKSPACE = pathlib.Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
_WORKTREE = _WORKSPACE / ".mutation_testing/worker-0"
_FIXTURES = "//tools/bazel_mutation_testing/testdata/rust"
_AREA = [f"{_FIXTURES}/..."]
# The timeout mutant waits this long.
_TEST_TIMEOUT = "10"
_TIMEOUT_FIXTURE = (
    _WORKTREE / "tools/bazel_mutation_testing/testdata/rust/times_out/lib.rs"
)


def _git(*arguments: str, environment: dict[str, str] | None = None) -> str:
    return subprocess.run(
        [bazel.executable("git"), *arguments],
        cwd=_WORKSPACE,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@contextlib.contextmanager
def _scratch_directory() -> Generator[pathlib.Path]:
    # Any Bazel command in the workspace deletes the temporary directory that
    # `bazel run` gives this test.
    parent = _WORKSPACE / ".mutation_testing"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        yield pathlib.Path(directory)


@pytest.fixture
def scratch() -> Generator[pathlib.Path]:
    with _scratch_directory() as directory:
        yield directory


@pytest.fixture(scope="module")
def commit() -> str:
    """Return a commit of the workspace as it is, with uncommitted changes."""
    with _scratch_directory() as directory:
        environment = {**os.environ, "GIT_INDEX_FILE": str(directory / "index")}
        _ = _git("read-tree", "HEAD", environment=environment)
        _ = _git("add", "--all", environment=environment)
        tree = _git("write-tree", environment=environment)
    return _git("commit-tree", "-p", "HEAD", "-m", "Mutation testing fixtures", tree)


def _tester_command(store: pathlib.Path, commit: str, area: list[str]) -> list[str]:
    return [
        str(runfiles.resolve_from_env("TESTER")),
        f"--store={store}",
        f"--commit={commit}",
        f"--test_timeout={_TEST_TIMEOUT}",
        *area,
    ]


def _tester_environment() -> dict[str, str]:
    # Bazel puts its output in TEST_TMPDIR when it is set, as it is in a test,
    # rather than reusing the worktree's server and output.
    return {name: value for name, value in os.environ.items() if name != "TEST_TMPDIR"}


def _run_tester(
    store: pathlib.Path, commit: str, area: list[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _tester_command(store, commit, area),
        env=_tester_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def _outcomes(store: pathlib.Path) -> list[str]:
    expected = frozenset(_expected_outcomes())
    lines = store.read_bytes().splitlines()[1:]
    outcomes: list[str] = []
    for line in lines:
        result = msgspec.json.decode(line, type=results.Result)
        with_culprit = f"{result.outcome} by {result.culprit}: {result.name}"
        # Several actions fail for some mutants, and which fails first varies
        # from run to run, so the expected outcomes name a culprit only when
        # one is certain. Otherwise they may name what rejected the mutant,
        # which every such action reports.
        evidence = (result.culprit or "").partition(" (")[2].removesuffix(")")
        with_evidence = f"{result.outcome} ({evidence}): {result.name}"
        if with_culprit in expected:
            outcomes.append(with_culprit)
        elif evidence and with_evidence in expected:
            outcomes.append(with_evidence)
        else:
            outcomes.append(f"{result.outcome}: {result.name}")
    return sorted(outcomes)


def _expected_outcomes() -> list[str]:
    expected = runfiles.resolve_from_env("EXPECTED_OUTCOMES")
    return sorted(expected.read_text(encoding="utf-8").splitlines())


def test_run_interrupted_mid_mutant_resumes_to_the_expected_outcomes(
    commit: str, scratch: pathlib.Path
):
    store = scratch / "results.jsonl"
    with subprocess.Popen(
        _tester_command(store, commit, _AREA),
        env=_tester_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8",
    ) as tester:
        # typeshed types Popen's output streams as IO[Any].
        output = cast("IO[str]", tester.stdout)
        # The timeout mutant stays applied for the whole test timeout.
        line = ""
        for line in output:
            if "replace += with *=" in line:
                break
        assert "replace += with *=" in line
        with pytest.raises(subprocess.TimeoutExpired):
            _ = tester.wait(timeout=2)
        assert "*=" in _TIMEOUT_FIXTURE.read_text(encoding="utf-8")
        tester.send_signal(signal.SIGINT)
    assert tester.returncode != 0
    assert _git("-C", str(_WORKTREE), "status", "--porcelain") == ""
    interrupted = _outcomes(store)
    assert not any("*=" in outcome for outcome in interrupted)

    completed = _run_tester(store, commit, _AREA)
    assert completed.returncode == 0, completed.stderr
    assert _outcomes(store) == _expected_outcomes()


def test_failing_baseline_stops_the_run(commit: str, scratch: pathlib.Path):
    store = scratch / "results.jsonl"
    completed = _run_tester(
        store,
        commit,
        [
            "//tools/bazel_mutation_testing/testdata/failing_baseline/...",
            "//tools/bazel_mutation_testing/testdata/failing_baseline:failing_baseline_test",
        ],
    )
    assert completed.returncode != 0
    assert (
        "BaselineFailedError: The area's tests fail without any mutant: "
        + "//tools/bazel_mutation_testing/testdata/failing_baseline:failing_baseline_test"
    ) in completed.stderr
    assert len(store.read_bytes().splitlines()) == 1


def test_concurrent_run_is_refused(commit: str, scratch: pathlib.Path):
    with (_WORKSPACE / ".mutation_testing/lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = _run_tester(scratch / "results.jsonl", commit, _AREA)
    assert completed.returncode != 0
    assert "RunInProgressError" in completed.stderr
    assert not (scratch / "results.jsonl").exists()
