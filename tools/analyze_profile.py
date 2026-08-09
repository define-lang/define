"""Inspect a raw Define compiler profiler snapshot."""

from __future__ import annotations

import pathlib

import click

from tools.profiler import schema


def _frame_text(frame: schema.Frame) -> str:
    # PRF-016: Source identity.
    return f"{frame['filename']}:{frame['line']} ({frame['function']})"


def emit_report(profile: schema.RawProfile) -> None:
    """Print the processes, threads, stacks, files, and functions in a profile."""
    # PRF-020: Machine and human interfaces.
    # PRF-043: Analyzer at every checkpoint.
    status = "successful" if profile["success"] else "unsuccessful"
    completeness = "complete" if profile["complete"] else "incomplete"
    print(f"Profile schema: {profile['schema_version']}; {completeness}; {status}")
    print(f"Command: {' '.join(profile['command'])}")
    print(f"Working directory: {profile['working_directory']}")
    print(
        f"Workload: {profile['workload_path']} "
        + f"(sha256 {profile['workload_sha256']})"
    )
    print(
        f"Process {profile['snapshot']['process_id'] if profile['snapshot'] else 'unknown'}: "
        + f"launcher {profile['launcher_executable']['path']}"
    )
    runtime = profile["python_runtime"]
    if runtime is None:
        print("Python runtime: not observed")
    else:
        threading_mode = "free-threaded" if runtime["free_threaded"] else "GIL-enabled"
        print(
            f"Python runtime: {runtime['version']} {threading_mode}; "
            + runtime["executable"]["path"]
        )

    counts = profile["observation_counts"]
    print(
        "Observations: "
        + f"{counts['successful']} successful, {counts['discarded']} discarded, "
        + f"{counts['missed']} missed, {counts['attempted']} attempted"
    )
    print(
        f"Compiler exit status: {profile['compiler_exit_status']}; "
        + f"diagnostics: {profile['diagnostics_status']}"
    )
    snapshot = profile["snapshot"]
    if snapshot is None:
        print("Snapshot: unavailable")
    else:
        print(
            f"Snapshot: {len(snapshot['threads'])} Python threads; "
            + f"profiler pause {snapshot['pause_duration_ns'] / 1_000_000:.3f} ms; "
            + f"target running {snapshot['target_running_ns'] / 1_000_000:.3f} ms"
        )
        for thread in snapshot["threads"]:
            print(
                f"\nThread {thread['os_thread_id']} "
                + f"(state {thread['stopped_state']}):"
            )
            for frame in thread["stack"]:
                print(f"  {_frame_text(frame)}")

        files = sorted(
            {
                frame["filename"]
                for thread in snapshot["threads"]
                for frame in thread["stack"]
            }
        )
        functions = sorted(
            {
                _frame_text(frame)
                for thread in snapshot["threads"]
                for frame in thread["stack"]
            }
        )
        print(f"\nFiles ({len(files)}):")
        for filename in files:
            print(f"  {filename}")
        print(f"\nFunctions ({len(functions)}):")
        for function in functions:
            print(f"  {function}")

    if profile["failures"]:
        print(f"\nFailures ({len(profile['failures'])}):")
        for failure in profile["failures"]:
            print(f"  {failure['kind']}: {failure['reason']}")


# PRF-020: Machine and human interfaces.
@click.command(
    epilog=(
        "This checkpoint reports the exact independent stack snapshot in raw "
        "capture order. It does not infer durations, calls, or thread lifetime."
    )
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(
        path_type=pathlib.Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    required=True,
    help="Raw JSON profile produced by //tools/profiler:__main__.",
)
def main(profile_path: pathlib.Path):
    """Inspect one raw profiler snapshot."""
    # PRF-020: Machine and human interfaces.
    # PRF-043: Analyzer at every checkpoint.
    try:
        profile = schema.load(profile_path)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    emit_report(profile)


# PRF-020: Machine and human interfaces.
if __name__ == "__main__":
    main()
