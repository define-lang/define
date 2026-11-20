"""Mutation-test an area of the repository with Bazel.

Run it with:
    bazelisk run //tools/bazel_mutation_testing:tester -- //define/... //crates/...
"""

from __future__ import annotations

import collections
import concurrent.futures
import contextlib
import fcntl
import functools
import os
import pathlib
from typing import TYPE_CHECKING

import click

from tools import runfiles
from tools.bazel_mutation_testing import (
    canary,
    lint_flags,
    pool,
    results,
    survivors,
    worker,
)
from tools.bazel_mutation_testing.python import generator as python_generator
from tools.bazel_mutation_testing.python import sources
from tools.bazel_mutation_testing.rust import crates
from tools.bazel_mutation_testing.rust import generator as rust_generator

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
    work: worker.Worker,
    area_crates: Iterable[crates.Crate],
    python_sources: sources.Sources,
) -> list[mutant.Mutant]:
    tracked_paths = work.tracked_paths()
    cargo_mutants = runfiles.resolve_from_env("CARGO_MUTANTS")
    cargo = runfiles.resolve_from_env("CARGO")
    mutants: list[mutant.Mutant] = []
    for crate in area_crates:
        mutants.extend(
            rust_generator.list_mutants(
                crate,
                workspace=work.worktree,
                tracked_paths=tracked_paths,
                cargo_mutants=cargo_mutants,
                cargo=cargo,
            )
        )
    mutants.extend(
        python_generator.list_mutants(
            python_sources.paths,
            workspace=work.worktree,
            tracked_paths=tracked_paths,
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
    help="The results store, relative to the workspace. A run resumes from it, "
    + "and writes its survivors report next to it, as <store>.survivors.md.",
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
# Six workers' Bazel servers held 17 GB of memory, which ran the machine out of
# memory alongside its other programs. Four workers left a sixth of the CPU
# idle.
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    help="The number of worktrees that test mutants at once, each with its own Bazel server.",
)
def main(
    area: tuple[str, ...],
    store: pathlib.Path,
    commit: str,
    test_timeout: int,
    workers: int,
):
    """Mutation-test the area that the target patterns AREA name.

    Mutates the Rust and Python sources of the targets that AREA matches, and
    runs AREA's tests on each mutant.
    """
    repository = pathlib.Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    run = results.Run(
        commit=worker.commit_id(repository, commit),
        area=list(area),
        test_timeout=test_timeout,
        lint_flags=lint_flags.load().bazel_flags(),
    )
    with (
        _exclusive(repository),
        results.Store(repository / store, run) as results_store,
    ):
        mutants = _test_area(repository, run, results_store, workers)
        _report(results_store)
        report = (repository / store).with_suffix(".survivors.md")
        survivors.write(report, run, mutants, results_store.results)
        click.echo(f"Survivors report: {report}")


def _testing(index: int, mutated: mutant.Mutant):
    click.echo(f"worker-{index}: testing {mutated.name}")


def _prepare(work: worker.Worker):
    work.prepare()
    # A worker's baseline reuses the first worker's cached results. It loads
    # the worker's Bazel server, so that the worker's first mutant is not slow.
    work.test_baseline()


def _test_area(
    repository: pathlib.Path,
    run: results.Run,
    results_store: results.Store,
    worker_count: int,
) -> list[mutant.Mutant]:
    # A fresh worktree's first build takes seconds from the cache, while a kept
    # worktree and its Bazel output base take a gigabyte of disk.
    with contextlib.ExitStack() as removals:
        workers: list[worker.Worker] = []
        for index in range(worker_count):
            work = worker.Worker(
                repository=repository,
                run=run,
                index=index,
                testing=functools.partial(_testing, index),
            )
            workers.append(work)
            _ = removals.callback(work.remove)
        return _test_on_workers(workers, run, results_store)


def _test_on_workers(
    workers: list[worker.Worker], run: results.Run, results_store: results.Store
) -> list[mutant.Mutant]:
    first = workers[0]
    # The other workers wait for the first worker's baseline, so that they
    # find its results in the cache rather than run the same tests at once.
    _prepare(first)
    with concurrent.futures.ThreadPoolExecutor(len(workers)) as executor:
        preparing = [executor.submit(_prepare, work) for work in workers[1:]]
        mutants = _list_and_check(first, run, results_store)
        for prepared in preparing:
            prepared.result()

    pending = [listed for listed in mutants if listed.name not in results_store.results]

    def record(result: results.Result):
        results_store.add(result)
        culprit = f" by {result.culprit}" if result.culprit else ""
        click.echo(
            f"[{len(results_store.results)}/{len(mutants)}] {result.name}: "
            + f"{result.outcome}{culprit} in {result.seconds:.1f} s"
        )

    pool.test_all(workers, pending, record)
    return mutants


def _list_and_check(
    work: worker.Worker, run: results.Run, results_store: results.Store
) -> list[mutant.Mutant]:
    """List the area's mutants, and check that the run's tests kill a canary."""
    area_crates = crates.find(work.worktree, run.area)
    python_sources = sources.find(work.worktree, run.area)
    mutants = _list_mutants(work, area_crates, python_sources)
    unlisted = set(results_store.results) - {listed.name for listed in mutants}
    if unlisted:
        raise UnlistedResultError(sorted(unlisted))

    run_canary = canary.make(area_crates, python_sources.tests, work.worktree)
    canary_result = work.test(run_canary.mutant)
    # Any failure kills a mutant, but only a failed test shows that the run's
    # tests detect a change. A timeout or running out of memory would not show
    # it either.
    if (
        canary_result.outcome != results.Outcome.KILLED
        or canary_result.culprit not in run_canary.tests
    ):
        raise CanaryNotKilledError(
            f"{canary_result.name}: {canary_result.outcome} {canary_result.culprit}"
        )
    return mutants


def _report(results_store: results.Store):
    outcomes = collections.Counter(
        result.outcome for result in results_store.results.values()
    )
    click.echo(
        f"{len(results_store.results)} mutants: "
        + ", ".join(f"{outcomes[outcome]} {outcome}" for outcome in results.Outcome)
    )
    for result in results_store.results.values():
        if result.outcome in survivors.REPORTED:
            click.echo(f"{result.outcome}: {result.name}")


if __name__ == "__main__":
    main()
