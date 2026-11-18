"""Mutation-test an area of the repository with Bazel.

Run it with:
    bazelisk run //tools/bazel_mutation_testing:tester -- //define/... //crates/...
"""

from __future__ import annotations

import collections
import contextlib
import fcntl
import os
import pathlib
from typing import TYPE_CHECKING

import click

from tools import runfiles
from tools.bazel_mutation_testing import lint_flags, results, worker
from tools.bazel_mutation_testing.rust import canary, crates, generator

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from tools.bazel_mutation_testing import mutant


class RunInProgressError(Exception):
    """Another run is using the repository's workers."""


class CanaryNotKilledError(Exception):
    """The canary's test did not fail."""


class DuplicateMutantError(Exception):
    """Two mutants have the same name."""


class UnlistedResultError(Exception):
    """The results store has results for mutants that the run did not list."""


def _list_mutants(
    work: worker.Worker, area_crates: Iterable[crates.Crate]
) -> list[mutant.Mutant]:
    tracked_paths = work.tracked_paths()
    cargo_mutants = runfiles.resolve_from_env("CARGO_MUTANTS")
    cargo = runfiles.resolve_from_env("CARGO")
    mutants: list[mutant.Mutant] = []
    for crate in area_crates:
        mutants.extend(
            generator.list_mutants(
                crate,
                workspace=work.worktree,
                tracked_paths=tracked_paths,
                cargo_mutants=cargo_mutants,
                cargo=cargo,
            )
        )
    names = collections.Counter(listed.name for listed in mutants)
    duplicates = [name for name, count in names.items() if count > 1]
    if duplicates:
        raise DuplicateMutantError(f"Mutants listed more than once: {duplicates}")
    return mutants


@contextlib.contextmanager
def _exclusive(repository: pathlib.Path) -> Generator[None]:
    """Hold the lock on the repository's workers until the block ends.

    Raises:
        RunInProgressError: Another run holds the lock.
    """
    # Runs share the workers' worktrees, so two runs at once would revert each
    # other's mutants.
    lock_path = repository / ".mutation_testing/lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("ab") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RunInProgressError(
                f"Another run holds {lock_path}. Wait for it to finish."
            ) from error
        yield


@click.command()
@click.argument("area", nargs=-1, required=True)
@click.option(
    "--store",
    type=click.Path(path_type=pathlib.Path),
    default=".mutation_testing/results.jsonl",
    help="The results store, relative to the workspace. A run resumes from it.",
)
@click.option(
    "--commit",
    default="HEAD",
    help="The commit to test.",
)
@click.option(
    "--test_timeout",
    type=int,
    default=60,
    help="The timeout of every test, in seconds.",
)
def main(area: tuple[str, ...], store: pathlib.Path, commit: str, test_timeout: int):
    """Mutation-test the area that the target patterns AREA name.

    Mutates the Rust sources of the targets that AREA matches, and runs AREA's
    tests on each mutant.
    """
    repository = pathlib.Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    run = results.Run(
        commit=worker.commit_id(repository, commit),
        area=list(area),
        test_timeout=test_timeout,
        allowed_lints=sorted(lint_flags.load().turned_off),
    )
    with (
        _exclusive(repository),
        results.Store(repository / store, run) as results_store,
    ):
        _test_area(repository, run, results_store)
        _report(results_store)


def _test_area(
    repository: pathlib.Path, run: results.Run, results_store: results.Store
):
    work = worker.Worker(repository=repository, run=run)
    work.prepare()
    work.test_baseline()
    area_crates = crates.find(work.worktree, run.area)
    mutants = _list_mutants(work, area_crates)
    unlisted = set(results_store.results) - {listed.name for listed in mutants}
    if unlisted:
        raise UnlistedResultError(sorted(unlisted))

    run_canary = canary.make(area_crates, work.worktree)
    canary_result = work.test(run_canary.mutant)
    # Any failure kills a mutant, but only a failed test shows that the run's
    # tests detect a change. A timeout would not show it either.
    if (
        canary_result.outcome != results.Outcome.KILLED
        or canary_result.culprit not in run_canary.tests
    ):
        raise CanaryNotKilledError(
            f"{canary_result.name}: {canary_result.outcome} {canary_result.culprit}"
        )

    for index, listed in enumerate(mutants, 1):
        if listed.name in results_store.results:
            continue
        click.echo(f"[{index}/{len(mutants)}] {listed.name}")
        result = work.test(listed)
        results_store.add(result)
        culprit = f" by {result.culprit}" if result.culprit else ""
        click.echo(f"    {result.outcome}{culprit} in {result.seconds:.1f} s")


def _report(results_store: results.Store):
    outcomes = collections.Counter(
        result.outcome for result in results_store.results.values()
    )
    click.echo(
        f"{len(results_store.results)} mutants: "
        + ", ".join(f"{outcomes[outcome]} {outcome}" for outcome in results.Outcome)
    )
    for result in results_store.results.values():
        if result.outcome in {results.Outcome.SURVIVED, results.Outcome.TIMED_OUT}:
            click.echo(f"{result.outcome}: {result.name}")


if __name__ == "__main__":
    main()
