"""Regenerate checked-in profiler analysis fixtures."""

from __future__ import annotations

import concurrent.futures
import itertools
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from tools.profiler import tachyon_profile, tachyon_profiler

if TYPE_CHECKING:
    from collections.abc import Callable

# Tachyon reports no sampling progress, so each phase runs long enough for
# dozens of samples at the profiler's default frequency. Every capture is then
# validated, and rejected captures are retried.
_PHASE_SECONDS = 0.05
_MAX_CAPTURE_ATTEMPTS = 10


def _coordinate(status_path: Path, control_path: Path, phases: bytes):
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
            # Tachyon offers no sampling-progress signal to wait on instead.
            # ast-grep-ignore: no-sleep
            time.sleep(_PHASE_SECONDS)
            _ = control_stream.write(b"1")


def _capture_phased_profile(
    profile_path: Path,
    source: Path,
    workspace: Path,
    phases: bytes,
) -> tachyon_profile.WallProfile:
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        status_path = temporary_path / "status"
        control_path = temporary_path / "control"
        os.mkfifo(status_path)
        os.mkfifo(control_path)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            coordinator = executor.submit(
                _coordinate, status_path, control_path, phases
            )
            exit_status = tachyon_profiler.capture(
                command=(
                    sys.executable,
                    str(source),
                    str(status_path),
                    str(control_path),
                ),
                profile_path=profile_path,
                working_directory=workspace,
                environment=dict(os.environ),
                stdin=None,
            )
            coordinator.result()
    if exit_status != 0:
        raise RuntimeError(f"{source} exited with status {exit_status}")
    return tachyon_profile.load(profile_path)


_STAGES = ("_stage_one_work", "_stage_two_work", "_stage_three_work", "_final_work")
_MINIMUM_STAGE_SAMPLES = 20


def _stages_are_captured(profile: tachyon_profile.WallProfile) -> bool:
    # Each stage of the chain must be sampled working, in order, on its thread.
    working_times: dict[str, list[int]] = {stage: [] for stage in _STAGES}
    for samples in profile.samples_by_thread.values():
        for sample in samples:
            if not sample.is_working:
                continue
            functions = {profile.frames[frame_id].function for frame_id in sample.stack}
            for stage in _STAGES:
                if stage in functions:
                    working_times[stage].append(sample.interval.start_ns)
    if any(len(times) < _MINIMUM_STAGE_SAMPLES for times in working_times.values()):
        return False
    stage_spans = [(min(times), max(times)) for times in working_times.values()]
    return all(
        earlier[1] < later[0] for earlier, later in itertools.pairwise(stage_spans)
    )


def _regenerate_phased_profile(
    testdata: Path,
    workspace: Path,
    name: str,
    phases: bytes,
    validator: Callable[[tachyon_profile.WallProfile], bool],
):
    profile_path = testdata / f"{name}_profile.bin"
    source = testdata / f"{name}_target.py"
    for _ in range(_MAX_CAPTURE_ATTEMPTS):
        profile = _capture_phased_profile(profile_path, source, workspace, phases)
        if validator(profile):
            print(f"Regenerated {profile_path.relative_to(workspace)}")
            return
    raise RuntimeError(f"could not capture the required {name} evidence")


def main():
    """Regenerate and validate every checked-in profile."""
    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    _regenerate_phased_profile(
        workspace / "tools/profiler/testdata",
        workspace,
        "critical_path",
        b"1234",
        _stages_are_captured,
    )


if __name__ == "__main__":
    main()
