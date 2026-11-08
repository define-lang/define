"""Time two checkouts' compilers on one input and check they generate the same code."""

from __future__ import annotations

import contextlib
import hashlib
import os
import pathlib
import statistics
import subprocess
import tempfile
import time

import click
import msgspec

from tools import profile_orchestration


class _Run(msgspec.Struct, frozen=True):
    seconds: float
    peak_rss_kb: int


class _Outcome(msgspec.Struct, frozen=True):
    """What a compile produced, which must not differ between the checkouts."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    # Each generated file's digest, by its path below the generated code
    # directory.
    generated_digests: dict[str, str]


class _Compiler(msgspec.Struct, frozen=True):
    name: str
    checkout: pathlib.Path
    launcher: pathlib.Path
    build_stamp: int


def _build_stamp(launcher: pathlib.Path) -> int:
    # The runfiles link most sources straight to the checkout, so editing a
    # source changes the compiler as surely as a rebuild does.
    runfiles = launcher.with_name(launcher.name + ".runfiles")
    manifest = launcher.with_name(launcher.name + ".runfiles_manifest")
    files: list[tuple[str, int, int]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        runfile, _, _ = line.partition(" ")
        status = (runfiles / runfile).stat()
        files.append((runfile, status.st_mtime_ns, status.st_size))
    return hash((launcher.stat().st_mtime_ns, tuple(files)))


def _generated_digests(directory: pathlib.Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            digests[path.relative_to(directory).as_posix()] = digest
    return digests


def _run(
    invocation: profile_orchestration.CompilerInvocation,
    logs: pathlib.Path,
) -> tuple[_Run, int]:
    with contextlib.ExitStack() as contexts:
        stdin = (
            subprocess.DEVNULL
            if invocation.stdin_path is None
            else contexts.enter_context(invocation.stdin_path.open("rb"))
        )
        stdout = contexts.enter_context((logs / "stdout").open("wb"))
        stderr = contexts.enter_context((logs / "stderr").open("wb"))
        started = time.perf_counter()
        process = subprocess.Popen(
            invocation.command,
            cwd=invocation.working_directory,
            env=profile_orchestration.target_environment(),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )
        # wait4 reports this child's own peak memory, which the cumulative
        # resource usage of all children does not.
        _, status, usage = os.wait4(process.pid, 0)
        seconds = time.perf_counter() - started
        # Popen did not reap the child, so it must not wait for it again.
        process.returncode = os.waitstatus_to_exitcode(status)
    return _Run(seconds=seconds, peak_rss_kb=usage.ru_maxrss), process.returncode


def _measure(
    compiler: _Compiler, request: _Request, scratch: pathlib.Path
) -> tuple[_Run, _Outcome]:
    output_dir = scratch / compiler.name
    output_dir.mkdir()
    invocation = profile_orchestration.compiler_invocation(
        compiler.checkout,
        compiler.launcher,
        request.source_path,
        request.project,
        request.entry,
        output_dir,
        request.max_threads,
    )
    run, exit_code = _run(invocation, scratch)
    outcome = _Outcome(
        exit_code=exit_code,
        stdout=(scratch / "stdout").read_bytes(),
        stderr=(scratch / "stderr").read_bytes(),
        generated_digests=_generated_digests(output_dir),
    )
    try:
        changed = _build_stamp(compiler.launcher) != compiler.build_stamp
    # A rebuild removes and recreates the runfiles.
    except FileNotFoundError:
        changed = True
    if changed:
        raise click.ClickException(
            f"the {compiler.name} compiler in {compiler.checkout} or its "
            + "sources changed while it was being timed, such as by another "
            + "Bazel command in that checkout"
        )
    return run, outcome


def _difference(baseline: _Outcome, candidate: _Outcome) -> str | None:
    if baseline.exit_code != candidate.exit_code:
        return f"exit {baseline.exit_code} became {candidate.exit_code}"
    if baseline.stdout != candidate.stdout:
        return "standard output differs"
    if baseline.stderr != candidate.stderr:
        return "standard error differs"
    baseline_paths = set(baseline.generated_digests)
    candidate_paths = set(candidate.generated_digests)
    if baseline_paths != candidate_paths:
        changed = sorted(baseline_paths ^ candidate_paths)
        return f"{len(changed)} generated files exist in only one, such as {changed[0]}"
    for path, digest in baseline.generated_digests.items():
        if candidate.generated_digests[path] != digest:
            return f"generated file {path} differs"
    return None


def _summary(name: str, runs: list[_Run]) -> str:
    seconds = [run.seconds for run in runs]
    peak_mb = max(run.peak_rss_kb for run in runs) / 1024
    return (
        f"{name:9} median {statistics.median(seconds):7.3f} s  "
        + f"mean {statistics.mean(seconds):7.3f}  "
        + f"stdev {statistics.stdev(seconds):6.3f}  "
        + f"min {min(seconds):7.3f}  max {max(seconds):7.3f}  "
        + f"peak RSS {peak_mb:,.0f} MB"
    )


class _Request(msgspec.Struct, frozen=True):
    source_path: pathlib.Path | None
    project: pathlib.Path | None
    entry: str
    max_threads: int | None


@click.command(
    epilog=(
        "Builds each checkout's compiler with --config=profiling, then runs "
        "them in alternating order, a fresh generated code directory each "
        "time, so that load on the machine affects both alike. Fails if the "
        "two differ in exit code, standard output, standard error, or any "
        "generated file, or if either compiler or its sources change while "
        "it is being timed, so nothing else may run Bazel in either checkout "
        "meanwhile. Peak RSS is each compile's maximum resident memory. "
        "Needs a POSIX system."
    )
)
@click.option(
    "--baseline",
    type=click.Path(path_type=pathlib.Path, exists=True, file_okay=False),
    required=True,
    help="Checkout or worktree whose compiler is the reference.",
)
@click.option(
    "--candidate",
    type=click.Path(path_type=pathlib.Path, exists=True, file_okay=False),
    required=True,
    help="Checkout or worktree whose compiler is compared with the baseline.",
)
@click.option(
    "--source",
    "source_path",
    type=click.Path(path_type=pathlib.Path, exists=True, dir_okay=False),
    help="Compile one .dfn file.",
)
@click.option(
    "--project",
    type=click.Path(path_type=pathlib.Path, exists=True, file_okay=False),
    help="Compile a project directory.",
)
@click.option(
    "--entry",
    default="test.dfn",
    show_default=True,
    help="Entry file within --project. Ignored by --source.",
)
@click.option(
    "--rounds",
    type=click.IntRange(min=2),
    default=5,
    show_default=True,
    help="Timed compiles of each checkout, after one untimed warm-up.",
)
@click.option(
    "--max-threads",
    type=click.IntRange(min=1),
    help="Passed to the compiler. Defaults to the compiler's own default.",
)
def main(  # noqa: PLR0913, PLR0917 - Click passes the declared command options.
    baseline: pathlib.Path,
    candidate: pathlib.Path,
    source_path: pathlib.Path | None,
    project: pathlib.Path | None,
    entry: str,
    rounds: int,
    max_threads: int | None,
):
    """Compare the compile time of two checkouts' compilers on one input."""
    if (source_path is None) == (project is None):
        raise click.UsageError("provide exactly one of --source or --project")
    request = _Request(
        source_path=None if source_path is None else source_path.absolute(),
        project=None if project is None else project.absolute(),
        entry=entry,
        max_threads=max_threads,
    )
    compilers: list[_Compiler] = []
    for name, checkout in (("baseline", baseline), ("candidate", candidate)):
        launcher = profile_orchestration.build_compiler(checkout.absolute())
        compilers.append(
            _Compiler(
                name=name,
                checkout=checkout.absolute(),
                launcher=launcher,
                build_stamp=_build_stamp(launcher),
            )
        )
    runs: dict[str, list[_Run]] = {compiler.name: [] for compiler in compilers}
    outcomes: dict[str, _Outcome] = {}
    # Round 0 warms the file system cache and is not timed.
    for round_index in range(rounds + 1):
        # Alternating which goes first cancels a steady drift in machine load.
        ordered = compilers if round_index % 2 == 0 else compilers[::-1]
        for compiler in ordered:
            with tempfile.TemporaryDirectory(prefix="define_compare_") as scratch:
                run, outcome = _measure(compiler, request, pathlib.Path(scratch))
            round_name = f"Round {round_index}" if round_index else "Warm-up"
            click.echo(
                f"{round_name} {compiler.name}: {run.seconds:.3f} s; "
                + f"peak RSS {run.peak_rss_kb / 1024:,.0f} MB"
            )
            if round_index:
                runs[compiler.name].append(run)
            if outcomes.setdefault(compiler.name, outcome) != outcome:
                raise click.ClickException(
                    f"the {compiler.name} compiler is not deterministic: "
                    + str(_difference(outcomes[compiler.name], outcome))
                )
        if round_index == 0:
            difference = _difference(outcomes["baseline"], outcomes["candidate"])
            if difference is not None:
                raise click.ClickException(f"the outputs differ: {difference}")
            click.echo(
                f"Outputs: identical; exit {outcomes['baseline'].exit_code}; "
                + f"{len(outcomes['baseline'].generated_digests)} generated files"
            )
    for compiler in compilers:
        click.echo(_summary(compiler.name, runs[compiler.name]))
    baseline_seconds = [run.seconds for run in runs["baseline"]]
    candidate_seconds = [run.seconds for run in runs["candidate"]]
    median_ratio = statistics.median(candidate_seconds) / statistics.median(
        baseline_seconds
    )
    click.echo(
        f"Candidate/baseline: median {median_ratio:.3f}; mean "
        + f"{statistics.mean(candidate_seconds) / statistics.mean(baseline_seconds):.3f}"
        + f"; min {min(candidate_seconds) / min(baseline_seconds):.3f}"
    )


if __name__ == "__main__":
    main()
