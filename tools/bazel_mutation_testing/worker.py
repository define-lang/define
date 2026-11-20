"""A worker: a worktree, with its own Bazel server, that tests mutants."""

from __future__ import annotations

import contextlib
import pathlib
import signal
import subprocess
import threading
import time
from typing import TYPE_CHECKING, final

import msgspec

from tools.bazel_mutation_testing import (
    bazel,
    build_events,
    coverage,
    diagnostics,
    results,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from tools.bazel_mutation_testing import mutant

# The remote execution service ends the standard error of an action that ran
# out of its memory limit with this text.
_OUT_OF_MEMORY = (
    "The remote execution service stopped this action"
    " because it ran out of its memory limit"
)

_BAZEL_EXIT_BUILD_FAILED = 1
_BAZEL_EXIT_TESTS_FAILED = 3
_BAZEL_EXIT_REMOTE_ERROR = 34

# A working Bazel server writes a build event each time a target finishes. A
# test runs for at most the run's test timeout, and the slowest action takes a
# few minutes. A server that writes no build event for longer than both has
# stopped responding.
_SLOWEST_ACTION_SECONDS = 4 * 60

# How often a worker checks whether its Bazel command still writes build
# events.
_PROGRESS_CHECK_SECONDS = 10

# A Bazel 9.3 server keeps every command's remote output checker, with the
# paths of every output that the command built, until its heap is full. A
# worker restarts its server after this many commands, long before then.
# TODO: Remove the restarts once the repository uses Bazel 9.4.0 or later,
# which include https://github.com/bazelbuild/bazel/pull/31731.
_COMMANDS_PER_SERVER = 200


class BaselineFailedError(Exception):
    """The area's tests fail without any mutant."""


class UnformattableMutantError(Exception):
    """The formatter rejects a mutated file, which no longer parses."""


class FormatterError(Exception):
    """The formatter failed for a reason other than the mutated file."""


class UnchangedMutantError(Exception):
    """A mutant does not change its file once the file is formatted."""


class NotAWorktreeError(Exception):
    """A worker's directory is not a worktree of the repository."""


class DirtyWorktreeError(Exception):
    """A worktree has changes after a mutant was reverted."""


class WorkerInterruptedError(Exception):
    """The run stopped the worker's mutant before its tests finished."""


class ServerFailedError(Exception):
    """A worker's Bazel server crashed or stopped responding."""


def _git(directory: pathlib.Path, *arguments: str) -> str:
    return subprocess.run(
        [bazel.executable("git"), *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def commit_id(repository: pathlib.Path, commit: str) -> str:
    """Return the full ID of the commit that `commit` names."""
    return _git(repository, "rev-parse", "--verify", f"{commit}^{{commit}}").strip()


def failed_result(
    name: str,
    failure: build_events.ActionFailure | build_events.TestFailure,
    seconds: float,
) -> results.Result:
    """Return the result of the mutant `name`, which `failure` killed."""
    culprit = failure.describe()
    if isinstance(failure, build_events.ActionFailure):
        output = failure.output
        found = diagnostics.action_rejections(failure.mnemonic, output)
        timed_out = False
    else:
        output = failure.log
        found = diagnostics.test_rejections(output)
        timed_out = failure.timed_out
    if _OUT_OF_MEMORY in output:
        outcome = results.Outcome.OUT_OF_MEMORY
    elif timed_out:
        outcome = results.Outcome.TIMED_OUT
    else:
        outcome = results.Outcome.KILLED
    if found:
        culprit += f" ({', '.join(sorted(found))})"
    return results.Result(name=name, outcome=outcome, culprit=culprit, seconds=seconds)


def _is_failed_build(
    exit_code: int, failure: build_events.ActionFailure | build_events.TestFailure
) -> bool:
    if exit_code in {_BAZEL_EXIT_BUILD_FAILED, _BAZEL_EXIT_TESTS_FAILED}:
        return True
    # Over remote execution, an action that does not create a declared output
    # fails the build with Bazel's remote error, as an outage does.
    return (
        exit_code == _BAZEL_EXIT_REMOTE_ERROR
        and isinstance(failure, build_events.ActionFailure)
        and failure.outputs_missing
    )


@final
class Worker:
    """Tests mutants one at a time in its own worktree."""

    def __init__(
        self,
        *,
        repository: pathlib.Path,
        run: results.Run,
        index: int,
        testing: Callable[[mutant.Mutant], None],
        server_failed: Callable[[ServerFailedError], None],
    ):
        """Test `run`'s mutants in the worktree of `repository` numbered `index`.

        The worker calls `testing` with each mutant once the mutant's tests
        have started. The worker calls `server_failed` when its Bazel server
        fails during a command, before the worker runs the command again on a
        new server.
        """
        self.name = f"worker-{index}"
        worktree = repository / f".mutation_testing/{self.name}"
        self.worktree = worktree
        self._testing = testing
        self._server_failed = server_failed
        self._repository = repository
        self._run = run
        self._build_event_file = worktree.parent / f"{worktree.name}.build_events.json"
        self._formatter = worktree / "bazel-bin/tools/format/format_/format"
        # The run interrupts a worker from another thread.
        self._lock = threading.Lock()
        self._interrupted = False
        self._tests: subprocess.Popen[str] | None = None
        self._output_base: pathlib.Path | None = None
        self._server_commands = 0
        self._test_patterns: list[str] = []

    def prepare(self):
        """Create or reset the worktree, build the formatter, and choose the targets to test.

        Raises:
            NotAWorktreeError: The worktree's directory exists, but is not a
                worktree of the repository.
            DirtyWorktreeError: The worktree has changes that checking out the
                commit does not remove.
        """
        if self.worktree.exists():
            self._require_worktree()
            _ = _git(self.worktree, "checkout", "--detach", "--force", self._run.commit)
        else:
            _ = _git(
                self._repository,
                "worktree",
                "add",
                "--detach",
                str(self.worktree),
                self._run.commit,
            )
        self._require_clean()
        self._output_base = bazel.output_base(self.worktree)
        _ = bazel.run_checked(
            self.worktree, ["build", "--build_runfile_links", "//tools/format"]
        )
        # A define_binary compiles a Define program that no test runs. A build
        # action has no timeout, so a mutant that makes the compiler loop
        # forever would stop its worker.
        programs = bazel.run_checked(
            self.worktree,
            [
                "query",
                "--",
                'kind("^define_binary rule$", '
                + f"{bazel.query_expression(self._run.area)})",
            ],
        ).split()
        self._test_patterns = [
            *self._run.area,
            *(f"-{program}" for program in programs),
        ]

    def remove(self):
        """Delete the worktree and its Bazel output base, and stop its Bazel server.

        Raises:
            NotAWorktreeError: The worktree's directory exists, but is not a
                worktree of the repository.
            DirtyWorktreeError: The worktree has changes.
        """
        self._build_event_file.unlink(missing_ok=True)
        if not self.worktree.exists():
            return
        self._require_worktree()
        # A worktree with changes shows what went wrong, so it is kept.
        self._require_clean()
        _ = bazel.run_checked(self.worktree, ["clean", "--expunge"])
        _ = _git(self._repository, "worktree", "remove", str(self.worktree))

    def tracked_paths(self) -> frozenset[str]:
        """Return the workspace-relative paths of the files Git tracks."""
        return frozenset(_git(self.worktree, "ls-files", "-z").split("\0")[:-1])

    def test_baseline(self):
        """Run the area's tests without any mutant.

        Raises:
            BaselineFailedError: A test or an action failed.
        """
        self._run_passing(self._test_arguments(frozenset()))

    def collect_coverage(self) -> coverage.Coverage:
        """Run the area's tests without any mutant, and return which tests run each line.

        Raises:
            BaselineFailedError: A test or an action failed.
        """
        arguments = [
            "coverage",
            # So that each test's build event names its coverage file, which
            # Bazel downloads from the remote execution service.
            f"--build_event_json_file={self._build_event_file}",
            "--experimental_build_event_upload_strategy=local",
            "--remote_download_regex=.*/coverage\\.dat$",
            "--",
            *self._test_patterns,
        ]
        self._run_passing(arguments)
        return coverage.from_reports(
            build_events.coverage_reports(self._build_event_file), self.worktree
        )

    def _run_passing(self, arguments: list[str]):
        """Run Bazel with `arguments`, which must pass.

        Raises:
            BaselineFailedError: A test or an action failed.
        """
        completed, failure = self._finish_on_working_server(
            self._start(arguments), arguments
        )
        if completed.returncode == 0:
            return
        if failure is None:
            raise bazel.BazelError(arguments, completed)
        raise BaselineFailedError(
            f"The area's tests fail without any mutant: {failure.describe()}"
        )

    def interrupt(self):
        """Stop the tests of the current mutant, and refuse to test any more."""
        with self._lock:
            self._interrupted = True
            if self._tests is not None:
                # On SIGINT, Bazel cancels the build rather than leaving its
                # server to finish it.
                self._tests.send_signal(signal.SIGINT)

    def usable(self) -> bool:
        """Return whether the worker can test another mutant: it is not interrupted, and its worktree has no changes."""
        with self._lock:
            if self._interrupted:
                return False
        return not _git(self.worktree, "status", "--porcelain")

    def kill(self):
        """Kill the worker's Bazel server, which ends its current Bazel command."""
        if self._output_base is None:
            # The worker has not started a Bazel server.
            return
        bazel.kill_server(self._output_base)

    def test(
        self, mutated: mutant.Mutant, selection: coverage.Selection
    ) -> results.Result:
        """Test `mutated` with the tests that `selection` chooses, and revert it.

        Raises:
            WorkerInterruptedError: The run interrupted the worker.
            FormatterError: The formatter failed for another reason than the
                mutated file.
            UnchangedMutantError: Formatting the mutated file undid the mutant.
            DirtyWorktreeError: Reverting the mutant left the worktree changed.
        """
        return msgspec.structs.replace(
            self._test_selected(mutated, selection.skipped),
            covering_tests=selection.covering_tests,
        )

    def _test_selected(
        self, mutated: mutant.Mutant, skipped: frozenset[str]
    ) -> results.Result:
        try:
            with self._applied(mutated):
                completed, failure, seconds = self._test_applied(mutated, skipped)
        except UnformattableMutantError:
            # Such a mutant could never be committed, as any failure shows.
            return results.Result(
                name=mutated.name,
                outcome=results.Outcome.KILLED,
                culprit="the formatter",
                seconds=0.0,
            )
        if completed.returncode == 0:
            return results.Result(
                name=mutated.name,
                outcome=results.Outcome.SURVIVED,
                culprit=None,
                seconds=seconds,
            )
        if failure is None or not _is_failed_build(completed.returncode, failure):
            raise bazel.BazelError(["test", *self._run.area], completed)
        return failed_result(mutated.name, failure, seconds)

    def _test_applied(
        self, mutated: mutant.Mutant, skipped: frozenset[str]
    ) -> tuple[
        subprocess.CompletedProcess[str],
        build_events.ActionFailure | build_events.TestFailure | None,
        float,
    ]:
        start = time.monotonic()
        arguments = self._test_arguments(skipped)
        tests = self._start(arguments)
        self._testing(mutated)
        completed, failure = self._finish_on_working_server(tests, arguments)
        return completed, failure, time.monotonic() - start

    @contextlib.contextmanager
    def _applied(self, mutated: mutant.Mutant) -> Generator[None]:
        path = self.worktree / mutated.path
        original = path.read_bytes()
        try:
            mutated.apply(self.worktree)
            formatted = self._format(mutated.path)
            if formatted.returncode != 0:
                # The formatter's errors have no structured form, so it
                # formats the unchanged file to tell whether the mutant or the
                # formatter is at fault.
                _ = path.write_bytes(original)
                if self._format(mutated.path).returncode != 0:
                    raise FormatterError(
                        f"Formatting {mutated.path} failed:\n{formatted.stderr}"
                    )
                raise UnformattableMutantError(mutated.name)
            if path.read_bytes() == original:
                raise UnchangedMutantError(mutated.name)
            yield
        finally:
            _ = path.write_bytes(original)
            # Also when a mutant fails partway, the next one needs a clean
            # worktree.
            self._require_clean()

    def _format(self, path: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._formatter, path],
            cwd=self.worktree,
            env=bazel.child_environment(
                BUILD_WORKSPACE_DIRECTORY=str(self.worktree),
                BUILD_WORKING_DIRECTORY=str(self.worktree),
            ),
            capture_output=True,
            text=True,
            check=False,
        )

    def _test_arguments(self, skipped: frozenset[str]) -> list[str]:
        """Return the arguments that run the area's tests other than `skipped`."""
        return [
            "test",
            f"--test_timeout={self._run.test_timeout}",
            *self._shared_arguments(),
            *self._test_patterns,
            *(f"-{test}" for test in sorted(skipped)),
        ]

    def _shared_arguments(self) -> list[str]:
        """Return the options of every test run, followed by "--"."""
        return [
            # These tests find the cases other tests must cover, or measure
            # what compiling costs rather than what it does.
            "--test_tag_filters=-no-coverage",
            # Most mutants are killed, so stopping at the first failure
            # ends most runs early.
            "--notest_keep_going",
            # Bazel 9 with Skymeld leaks a pool of 200 threads from each build
            # that fails before its analysis finishes, which many builds of a
            # new worker do. A worker's Bazel server then reaches tens of
            # thousands of threads.
            # TODO: Remove this flag once the repository uses a Bazel that
            # includes https://github.com/bazelbuild/bazel/pull/28657.
            "--noexperimental_merged_skyframe_analysis_execution",
            f"--build_event_json_file={self._build_event_file}",
            *self._run.lint_flags,
            # So that a failed action or pyright_test names what rejected
            # the mutant.
            "--@rules_rust//rust/settings:error_format=json",
            "--@rules_rust//rust/settings:clippy_error_format=json",
            "--//tools/bzl:lint_json",
            # So that each failed action's build event names a file that
            # holds its standard error, and each test's names its coverage.
            "--experimental_build_event_upload_strategy=local",
            "--",
        ]

    def _start(self, arguments: list[str]) -> subprocess.Popen[str]:
        """Start Bazel with `arguments`.

        Raises:
            WorkerInterruptedError: The run interrupted the worker.
        """
        if self._server_commands == _COMMANDS_PER_SERVER:
            _ = bazel.run_checked(self.worktree, ["shutdown"])
            self._server_commands = 0
        with self._lock:
            if self._interrupted:
                raise WorkerInterruptedError(self.worktree)
            tests = bazel.start(self.worktree, arguments)
            self._tests = tests
        self._server_commands += 1
        return tests

    def _finish_on_working_server(
        self, tests: subprocess.Popen[str], arguments: list[str]
    ) -> tuple[
        subprocess.CompletedProcess[str],
        build_events.ActionFailure | build_events.TestFailure | None,
    ]:
        """Wait for `tests`, which Bazel runs with `arguments`, and return Bazel's output and the first failure.

        A server's failure says nothing about what the server builds, so when
        the server fails, the worker runs `arguments` again on a new server.

        Raises:
            WorkerInterruptedError: The run interrupted the worker.
            ServerFailedError: The new server failed too.
        """
        try:
            return self._finish_tests(tests)
        except ServerFailedError as error:
            self._server_failed(error)
        self._server_commands = 0
        return self._finish_tests(self._start(arguments))

    def _finish_tests(
        self, tests: subprocess.Popen[str]
    ) -> tuple[
        subprocess.CompletedProcess[str],
        build_events.ActionFailure | build_events.TestFailure | None,
    ]:
        """Wait for `tests`, and return Bazel's output and the first failure.

        Raises:
            WorkerInterruptedError: The run interrupted the worker.
            ServerFailedError: The Bazel server crashed or stopped responding.
        """
        silent_seconds = self._run.test_timeout + _SLOWEST_ACTION_SECONDS
        progress = bazel.Progress(
            self._build_event_file, silent_seconds, time.monotonic
        )
        responded = True
        with tests:
            while True:
                try:
                    stdout, stderr = tests.communicate(timeout=_PROGRESS_CHECK_SECONDS)
                    break
                except subprocess.TimeoutExpired:
                    if not progress.stalled():
                        continue
                # A Bazel client exits once its server is gone.
                self.kill()
                stdout, stderr = tests.communicate()
                responded = False
                break
        completed = subprocess.CompletedProcess(
            tests.args, tests.returncode, stdout, stderr
        )
        with self._lock:
            self._tests = None
            if self._interrupted:
                raise WorkerInterruptedError(self.worktree)
        if not responded:
            raise ServerFailedError(
                f"Bazel wrote no build events for {silent_seconds} seconds"
            )
        if completed.returncode in bazel.SERVER_FAILURE_EXIT_CODES:
            raise ServerFailedError(
                f"Bazel exited with {completed.returncode}\n{completed.stderr}"
            )
        return completed, build_events.first_failure(self._build_event_file)

    def _require_worktree(self):
        # In any other directory, or through a symlink to another checkout, a
        # forced checkout would discard that checkout's changes.
        location = self._repository.resolve() / self.worktree.relative_to(
            self._repository
        )
        if self.worktree.resolve() != location:
            raise NotAWorktreeError(f"{self.worktree} is a symlink")
        top, git_directory, common = _git(
            self.worktree,
            "rev-parse",
            "--path-format=absolute",
            "--show-toplevel",
            "--git-dir",
            "--git-common-dir",
        ).split("\n")[:3]
        repository_common = _git(
            self._repository, "rev-parse", "--path-format=absolute", "--git-common-dir"
        ).strip()
        # A linked worktree has its own Git directory; the main checkout's is
        # the common one. Git writes Windows paths with forward slashes, which
        # pathlib compares equal to backslashes.
        if (pathlib.Path(top), pathlib.Path(common)) != (
            location,
            pathlib.Path(repository_common),
        ) or pathlib.Path(git_directory) == pathlib.Path(common):
            raise NotAWorktreeError(
                f"{self.worktree} is not a linked worktree of {self._repository}"
            )

    def _require_clean(self):
        status = _git(self.worktree, "status", "--porcelain")
        if status:
            raise DirtyWorktreeError(f"{self.worktree} has changes:\n{status}")
