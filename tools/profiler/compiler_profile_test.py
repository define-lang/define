from __future__ import annotations

import click.testing

from tools import runfiles
from tools.profiler import analyzer


# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-047: Multi-threaded critical path.
def test_real_compiler_profile_reports_stackless_critical_intervals():
    analysis_result = click.testing.CliRunner().invoke(
        analyzer.main,
        [
            "--profile",
            str(runfiles.resolve_from_env("PROFILER_COMPILER_WALL_PROFILE")),
            "--limit",
            "1000",
        ],
    )

    assert analysis_result.exit_code == 0
    assert "critical thread had no Python stack" in analysis_result.output
