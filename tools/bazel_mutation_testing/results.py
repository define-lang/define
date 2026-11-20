"""The results store: one line per tested mutant, appended as each finishes."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, final

import msgspec

if TYPE_CHECKING:
    import pathlib


class Outcome(enum.StrEnum):
    """What testing a mutant found."""

    KILLED = "killed"
    SURVIVED = "survived"
    TIMED_OUT = "timed out"
    OUT_OF_MEMORY = "ran out of memory"
    ERROR = "error"
    """Testing the mutant failed on two workers, so the mutant has no outcome.
    A resumed run tests it again."""


class Run(msgspec.Struct, frozen=True):
    """What a store's results test: the first line of the store."""

    commit: str
    area: list[str]
    test_timeout: int
    """The timeout of every test, in seconds."""
    lint_flags: list[str]
    """The Bazel flags that turn lints and rules off in the run."""


class Result(msgspec.Struct, frozen=True):
    """The outcome of testing one mutant."""

    name: str
    outcome: Outcome
    culprit: str | None
    """The test or action that failed first, or for an error, what failed."""
    seconds: float
    covering_tests: int | None = None
    """How many of the tests that record coverage run the mutant's lines, or
    None when no coverage records them. Results from runs before the tester
    counted them have None too."""


class MismatchedRunError(Exception):
    """A store holds the results of a different run."""


class DuplicateResultError(Exception):
    """A store has two results for one mutant."""


@final
class Store:
    """A results store, which a run appends to and resumes from."""

    def __init__(self, path: pathlib.Path, run: Run):
        """Open the store at `path`, creating it for `run` if it is new.

        Raises:
            MismatchedRunError: The store holds the results of another run.
            DuplicateResultError: The store has two results for one mutant.
        """
        self.results: dict[str, Result] = {}
        if path.exists():
            self._load(path, run)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(msgspec.json.encode(run) + b"\n")
        self._file = path.open("ab")

    def _load(self, path: pathlib.Path, run: Run):
        data = path.read_bytes()
        header, _, body = data.partition(b"\n")
        try:
            stored_run = msgspec.json.decode(header, type=Run)
        except msgspec.ValidationError as error:
            raise MismatchedRunError(
                f"{path} was made by an older tester ({error}). "
                + "Delete it or choose another store."
            ) from error
        if stored_run != run:
            raise MismatchedRunError(
                f"{path} holds the results of {stored_run}, not {run}. "
                + "Delete it or choose another store."
            )
        complete_length = len(header) + 1
        for line in body.splitlines(keepends=True):
            # A record ends with its newline. Only the last one can be
            # unfinished, when a run stopped while writing it.
            if not line.endswith(b"\n"):
                break
            result = msgspec.json.decode(line, type=Result)
            earlier = self.results.get(result.name)
            # A resumed run tests a mutant with an error result again.
            if earlier is not None and earlier.outcome != Outcome.ERROR:
                raise DuplicateResultError(f"{path} has two results for {result.name}")
            self.results[result.name] = result
            complete_length += len(line)
        if complete_length < len(data):
            with path.open("r+b") as unfinished:
                _ = unfinished.truncate(complete_length)

    def __enter__(self) -> Store:
        """Return the store, which closes at the end of the `with` block."""
        return self

    def __exit__(self, *exception: object):
        """Close the store's file."""
        self._file.close()

    def add(self, result: Result):
        """Record `result`, so that it survives an interrupted run."""
        _ = self._file.write(msgspec.json.encode(result) + b"\n")
        self._file.flush()
        self.results[result.name] = result
