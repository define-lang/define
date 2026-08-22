from __future__ import annotations

import os
from pathlib import Path

import click.testing
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.profiler import analyzer


def _compiler_profile() -> Path:
    location = os.environ["PROFILER_COMPILER_WALL_PROFILE"]
    candidate = Path(location)
    if candidate.exists():
        return candidate
    runfiles_resolver = runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    resolved = runfiles_resolver.Rlocation(location)
    assert resolved is not None
    return Path(resolved)


# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-047: Multi-threaded critical path.
def test_real_compiler_profile_reports_stackless_critical_intervals():
    analysis_result = click.testing.CliRunner().invoke(
        analyzer.main,
        [
            "--profile",
            str(_compiler_profile()),
            "--limit",
            "1000",
        ],
    )

    assert analysis_result.exit_code == 0
    assert "critical thread had no Python stack" in analysis_result.output
