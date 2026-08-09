import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools import analyze_profile, run_profile
from tools.generators import generate_large_define_source

_CHILD_EXIT_ERRORS = {
    "Error: No child process (os error 10)",
    "Error: No child processes (os error 10)",
}
_CAPTURE_SUMMARY = re.compile(r"Samples: ([1-9][0-9]*) Errors: 0")
pytestmark = pytest.mark.skipif(
    sys.platform == "darwin",
    reason="py-spy requires root on macOS",
)


def _py_spy_executable() -> Path:
    runfiles_dir = Path(os.environ["RUNFILES_DIR"])
    return next(runfiles_dir.glob("*/install/bin/py-spy"))


def _record_profile(
    tmp_path: Path,
    profile_mode: run_profile.ProfileMode,
    capfd: pytest.CaptureFixture[str],
) -> Path:
    profile_path = tmp_path / f"{profile_mode}.json"
    source_path = tmp_path / "source.dfn"
    _ = generate_large_define_source.write_to_path(source_path, 50_000)
    returncode = 0
    try:
        run_profile.record_profile(
            (str(_py_spy_executable()),),
            Path("define/compiler/main").resolve(),
            None,
            source_path,
            Path.cwd(),
            profile_path,
            1,
            tmp_path / f"output_{profile_mode}",
            profile_mode,
        )
    except subprocess.CalledProcessError as error:
        returncode = error.returncode

    captured = capfd.readouterr()
    summary = _CAPTURE_SUMMARY.search(captured.out)
    assert summary is not None
    assert int(summary.group(1)) > 0
    for line in captured.out.splitlines():
        assert not line or line.startswith("py-spy>")
    if returncode == 0:
        assert captured.err == ""
    else:
        assert captured.err.strip() in _CHILD_EXIT_ERRORS
    return profile_path


def test_wall_profile_is_compatible_with_analyzer(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
):
    profile_path = _record_profile(tmp_path, run_profile.ProfileMode.WALL, capfd)

    wall_time, thread_count, segments = analyze_profile.load_segments(profile_path)

    assert wall_time > 0.0
    assert thread_count > 0
    assert segments
    compiler_frame_found = False
    for stack, _start, _end in segments:
        for filename, _line, _name in stack:
            if "/define/compiler/" in filename:
                compiler_frame_found = True
    assert compiler_frame_found


def test_cpu_profile_is_compatible_with_analyzer(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
):
    profile_path = _record_profile(tmp_path, run_profile.ProfileMode.CPU, capfd)

    wall_time, retained_samples, _omitted_samples, samples = (
        analyze_profile.load_cpu_samples(profile_path)
    )

    assert wall_time > 0.0
    assert retained_samples > 0
    assert samples
    compiler_frame_found = False
    for stack, _duration in samples:
        for filename, _line, _name in stack:
            if "/define/compiler/" in filename:
                compiler_frame_found = True
    assert compiler_frame_found
