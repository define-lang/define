"""Regenerate checked-in profiler analysis fixtures."""

import concurrent.futures
import contextlib
import io
import os
import select
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.generators import generate_large_define_source
from tools.profiler import analyzer, schema, wall_analyzer, wall_critical_path

_OBSERVATIONS_PER_PHASE = 20
_MAX_CAPTURE_ATTEMPTS = 10


class _CaptureRejectedError(Exception):
    """The profiler rejected a completed fixture capture."""


def _runfile(location: str) -> Path:
    runfiles_resolver = runfiles.Runfiles.Create()
    if runfiles_resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = runfiles_resolver.Rlocation(location)
    if resolved is None:
        raise FileNotFoundError(location)
    return Path(resolved)


def _wait_for_observations(
    event_file_descriptor: int,
    buffered: bytes,
) -> bytes:
    observed = 0
    while observed < _OBSERVATIONS_PER_PHASE:
        readable, _, _ = select.select([event_file_descriptor], [], [])
        if not readable:
            raise RuntimeError("profiler event stream became unreadable")
        event_bytes = os.read(event_file_descriptor, 4096)
        if not event_bytes:
            raise RuntimeError("profiler event stream closed before target release")
        buffered += event_bytes
        *lines, buffered = buffered.split(b"\n")
        observed += sum(line == b"successful-observation-persisted" for line in lines)
    return buffered


def _coordinate(
    status_path: Path,
    control_path: Path,
    event_file_descriptor: int,
    phases: bytes,
) -> None:
    buffered = b""
    with (
        status_path.open("rb", buffering=0) as status_stream,
        control_path.open("wb", buffering=0) as control_stream,
    ):
        for phase in phases:
            observed_phase = status_stream.read(1)
            if observed_phase != bytes([phase]):
                raise RuntimeError(
                    f"expected target phase {phase}, observed {observed_phase!r}"
                )
            buffered = _wait_for_observations(event_file_descriptor, buffered)
            _ = control_stream.write(b"1")


def _capture_command(
    profile_path: Path,
    workload_path: Path,
    workspace: Path,
    command: tuple[str, ...],
    *,
    event_file_descriptor: int | None = None,
    mean_interval_seconds: float = 0.001,
) -> schema.RawProfile:
    profiler_command = [
        str(_runfile("_main/tools/profiler/__main__")),
        "--profile",
        str(profile_path),
        "--workload",
        str(workload_path),
        "--working-directory",
        str(workspace),
        "--mean-interval-seconds",
        str(mean_interval_seconds),
    ]
    pass_file_descriptors: tuple[int, ...] = ()
    if event_file_descriptor is not None:
        profiler_command.extend(["--event-fd", str(event_file_descriptor)])
        pass_file_descriptors = (event_file_descriptor,)
    profiler_command.extend(["--", *command])
    capture_process = subprocess.run(
        profiler_command,
        capture_output=True,
        text=True,
        check=False,
        pass_fds=pass_file_descriptors,
    )
    if capture_process.returncode != 0:
        raise _CaptureRejectedError(capture_process.stdout + capture_process.stderr)
    return schema.load(profile_path)


def _capture_phased_profile(
    profile_path: Path,
    source: Path,
    workspace: Path,
    phases: bytes,
    mean_interval_seconds: float,
) -> schema.RawProfile:
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        status_path = temporary_path / "status"
        control_path = temporary_path / "control"
        os.mkfifo(status_path)
        os.mkfifo(control_path)
        event_read_file_descriptor, event_write_file_descriptor = os.pipe()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                coordinator = executor.submit(
                    _coordinate,
                    status_path,
                    control_path,
                    event_read_file_descriptor,
                    phases,
                )
                try:
                    profile = _capture_command(
                        profile_path,
                        source,
                        workspace,
                        (
                            "/bin/sh",
                            "-c",
                            'exec "$@"',
                            "profile-fixture",
                            str(Path("/proc/self/exe").resolve()),
                            str(source),
                            str(status_path),
                            str(control_path),
                        ),
                        event_file_descriptor=event_write_file_descriptor,
                        mean_interval_seconds=mean_interval_seconds,
                    )
                finally:
                    os.close(event_write_file_descriptor)
                coordinator.result()
        finally:
            os.close(event_read_file_descriptor)
    return profile


def _analysis(profile: schema.RawProfile) -> wall_analyzer.Analysis:
    analysis = analyzer.analyze(profile)
    if not isinstance(analysis, wall_analyzer.Analysis):
        raise TypeError("wall fixture produced a CPU analysis")
    return analysis


def _critical_path_is_resolved(profile: schema.RawProfile) -> bool:
    critical_path = _analysis(profile).critical_path
    resolved_handoffs = [
        handoff
        for handoff in critical_path.handoffs
        if isinstance(handoff, wall_critical_path.ResolvedHandoff)
    ]
    return len(resolved_handoffs) >= 3


def _handoff_is_ambiguous(profile: schema.RawProfile) -> bool:
    handoffs = _analysis(profile).critical_path.handoffs
    return bool(
        handoffs
        and isinstance(handoffs[0], wall_critical_path.UnresolvedHandoff)
        and handoffs[0].resolution == "ambiguous"
        and len(handoffs[0].candidates) == 2
    )


def _worker_waited_from_first_observation(profile: schema.RawProfile) -> bool:
    handoffs = _analysis(profile).critical_path.handoffs
    return bool(
        handoffs
        and isinstance(handoffs[0], wall_critical_path.ResolvedHandoff)
        and handoffs[0].downstream_wait_ns > 0
    )


def _handoff_is_unobserved(profile: schema.RawProfile) -> bool:
    handoffs = _analysis(profile).critical_path.handoffs
    return bool(
        handoffs
        and isinstance(handoffs[0], wall_critical_path.UnresolvedHandoff)
        and handoffs[0].resolution == "unobserved"
        and not handoffs[0].candidates
    )


def _continuous_lifecycles_are_observed(profile: schema.RawProfile) -> bool:
    analysis = _analysis(profile)
    rows = {row.identity.function: row for row in analysis.cumulative_function_rows}
    required_functions = {
        "_retired_worker",
        "_deep_wait_level_two",
        "_shallow_wait",
        "_high_call_frequency",
        "_low_call_frequency",
    }
    return bool(
        required_functions <= rows.keys()
        and rows["_retired_worker"].wall_occupancy_ns
        < rows["_deep_wait_level_two"].wall_occupancy_ns
        and rows["_retired_worker"].wall_occupancy_ns
        < rows["_shallow_wait"].wall_occupancy_ns
    )


def _regenerate_phased_profile(
    testdata: Path,
    workspace: Path,
    name: str,
    phases: bytes,
    validator: Callable[[schema.RawProfile], bool],
    *,
    mean_interval_seconds: float = 0.001,
) -> None:
    profile_path = testdata / f"{name}_profile.jsonl"
    source = testdata / f"{name}_target.py"
    last_capture_error: _CaptureRejectedError | None = None
    for _ in range(_MAX_CAPTURE_ATTEMPTS):
        try:
            profile = _capture_phased_profile(
                profile_path,
                source,
                workspace,
                phases,
                mean_interval_seconds,
            )
        except _CaptureRejectedError as error:
            last_capture_error = error
            continue
        if validator(profile):
            print(f"Regenerated {profile_path.relative_to(workspace)}")
            return
    raise RuntimeError(f"could not capture the required {name} evidence") from (
        last_capture_error
    )


def _regenerate_compiler_profile(
    testdata: Path,
    workspace: Path,
) -> None:
    temporary_root = workspace / "tmp"
    temporary_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_root) as temporary_directory:
        temporary_path = Path(temporary_directory)
        config_path = temporary_path / ".define/project/config.defcl"
        config_path.parent.mkdir(parents=True)
        _ = config_path.write_text(
            'project: { universe_name: "mv:define-lang.org:large_program" }\n',
            encoding="utf-8",
        )
        source = temporary_path / "compiler.dfn"
        _ = generate_large_define_source.write_to_path(source, 30_000)
        profile_path = testdata / "compiler_wall_profile.jsonl"
        last_capture_error: _CaptureRejectedError | None = None
        for attempt in range(_MAX_CAPTURE_ATTEMPTS):
            try:
                profile = _capture_command(
                    profile_path,
                    source,
                    temporary_path,
                    (
                        "/bin/sh",
                        "-c",
                        'source_path=$1; shift; exec "$@" < "$source_path"',
                        "compiler-fixture",
                        str(source),
                        str(_runfile("_main/define/compiler/main")),
                        "compile",
                        "--out",
                        str(temporary_path / f"output-{attempt}"),
                        "--max-threads",
                        "1",
                    ),
                    mean_interval_seconds=0.01,
                )
            except _CaptureRejectedError as error:
                last_capture_error = error
                continue
            report_stream = io.StringIO()
            with contextlib.redirect_stdout(report_stream):
                analyzer.emit_report(profile, _analysis(profile), 1000)
            if "critical thread had no Python stack" in report_stream.getvalue():
                print(f"Regenerated {profile_path.relative_to(workspace)}")
                return
    raise RuntimeError("compiler profile did not capture the required evidence") from (
        last_capture_error
    )


def main() -> None:
    """Regenerate and validate every checked-in raw profile."""
    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    testdata = workspace / "tools/profiler/testdata"
    _regenerate_phased_profile(
        testdata,
        workspace,
        "ambiguous_critical_path",
        b"123",
        _handoff_is_ambiguous,
    )
    _regenerate_phased_profile(
        testdata,
        workspace,
        "critical_path",
        b"1234",
        _critical_path_is_resolved,
    )
    _regenerate_phased_profile(
        testdata,
        workspace,
        "continuous",
        b"12",
        _continuous_lifecycles_are_observed,
        mean_interval_seconds=0.01,
    )
    _regenerate_phased_profile(
        testdata,
        workspace,
        "initial_wait_critical_path",
        b"123",
        _worker_waited_from_first_observation,
    )
    _regenerate_phased_profile(
        testdata,
        workspace,
        "unresolved_critical_path",
        b"12",
        _handoff_is_unobserved,
    )
    _regenerate_compiler_profile(testdata, workspace)


if __name__ == "__main__":
    main()
