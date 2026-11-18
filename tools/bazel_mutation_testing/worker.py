"""A worker: a worktree, with its own Bazel server, that tests mutants."""

from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING, final

from tools.bazel_mutation_testing import bazel, build_events, results

if TYPE_CHECKING:
    import pathlib

    from tools.bazel_mutation_testing import mutant

_BAZEL_EXIT_BUILD_FAILED = 1
_BAZEL_EXIT_TESTS_FAILED = 3


class BaselineFailedError(Exception):
    """The area's tests fail without any mutant."""


class UnchangedMutantError(Exception):
    """A mutant does not change its file once the file is formatted."""


class NotAWorktreeError(Exception):
    """A worker's directory is not a worktree of the repository."""


class DirtyWorktreeError(Exception):
    """A worktree has changes after a mutant was reverted."""


def _git(directory: pathlib.Path, *arguments: str, stdin: str | None = None) -> str:
    return subprocess.run(
        [bazel.executable("git"), *arguments],
        cwd=directory,
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def outcome(
    failure: build_events.ActionFailure | build_events.TestFailure,
) -> results.Outcome:
    """Return the outcome of a mutant whose first failure is `failure`."""
    if isinstance(failure, build_events.TestFailure) and failure.timed_out:
        return results.Outcome.TIMED_OUT
    return results.Outcome.KILLED


@final
class Worker:
    """Tests mutants one at a time in its own worktree."""

    def __init__(
        self,
        *,
        repository: pathlib.Path,
        worktree: pathlib.Path,
        run: results.Run,
    ):
        """Test `run`'s mutants in the worktree at `worktree`."""
        self.worktree = worktree
        self._repository = repository
        self._run = run
        self._build_event_file = worktree.parent / f"{worktree.name}.build_events.json"
        self._formatter = worktree / "bazel-bin/tools/format/format_/format"

    def prepare(self):
        """Create or reset the worktree, and build the formatter.

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
        _ = bazel.run_checked(
            self.worktree, ["build", "--build_runfile_links", "//tools/format"]
        )

    def tracked_paths(self) -> frozenset[str]:
        """Return the workspace-relative paths of the files Git tracks."""
        return frozenset(_git(self.worktree, "ls-files", "-z").split("\0")[:-1])

    def test_baseline(self):
        """Run the area's tests without any mutant.

        Raises:
            BaselineFailedError: A test or an action failed.
        """
        completed, failure = self._run_tests()
        if completed.returncode == 0:
            return
        if failure is None:
            raise bazel.BazelError(["test", *self._run.area], completed)
        raise BaselineFailedError(
            f"The area's tests fail without any mutant: {failure.describe()}"
        )

    def test(self, mutated: mutant.Mutant) -> results.Result:
        """Test `mutated`, and revert it.

        Raises:
            UnchangedMutantError: Formatting the mutated file undid the mutant.
            DirtyWorktreeError: Reverting the mutant left the worktree changed.
        """
        path = self.worktree / mutated.path
        original = path.read_bytes()
        try:
            _ = _git(self.worktree, "apply", stdin=mutated.patch)
            self._format(mutated.path)
            if path.read_bytes() == original:
                raise UnchangedMutantError(mutated.name)
            start = time.monotonic()
            completed, failure = self._run_tests()
            seconds = time.monotonic() - start
        finally:
            _ = path.write_bytes(original)
        self._require_clean()
        if completed.returncode == 0:
            return results.Result(
                name=mutated.name,
                outcome=results.Outcome.SURVIVED,
                culprit=None,
                seconds=seconds,
            )
        if failure is None or completed.returncode not in {
            _BAZEL_EXIT_BUILD_FAILED,
            _BAZEL_EXIT_TESTS_FAILED,
        }:
            raise bazel.BazelError(["test", *self._run.area], completed)
        return results.Result(
            name=mutated.name,
            outcome=outcome(failure),
            culprit=failure.describe(),
            seconds=seconds,
        )

    def _format(self, path: str):
        _ = subprocess.run(
            [self._formatter, path],
            cwd=self.worktree,
            env=bazel.child_environment(
                BUILD_WORKSPACE_DIRECTORY=str(self.worktree),
                BUILD_WORKING_DIRECTORY=str(self.worktree),
            ),
            capture_output=True,
            check=True,
        )

    def _run_tests(
        self,
    ) -> tuple[
        subprocess.CompletedProcess[str],
        build_events.ActionFailure | build_events.TestFailure | None,
    ]:
        completed = bazel.run(
            self.worktree,
            [
                "test",
                # These tests find the cases other tests must cover, or measure
                # what compiling costs rather than what it does.
                "--test_tag_filters=-no-coverage",
                # Most mutants are killed, so stopping at the first failure
                # ends most runs early.
                "--notest_keep_going",
                f"--test_timeout={self._run.test_timeout}",
                f"--build_event_json_file={self._build_event_file}",
                "--",
                *self._run.area,
            ],
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
        # the common one.
        if (top, common) != (str(location), repository_common) or (
            git_directory == common
        ):
            raise NotAWorktreeError(
                f"{self.worktree} is not a linked worktree of {self._repository}"
            )

    def _require_clean(self):
        status = _git(self.worktree, "status", "--porcelain")
        if status:
            raise DirtyWorktreeError(f"{self.worktree} has changes:\n{status}")
