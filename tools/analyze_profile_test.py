import json
from pathlib import Path
from unittest import mock

import click.testing
import pytest

from tools import analyze_profile


@pytest.fixture
def profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    _ = path.write_text(
        json.dumps(
            {
                "$schema": "https://www.speedscope.app/file-format-schema.json",
                "profiles": [
                    {
                        "type": "sampled",
                        "name": "Thread 1",
                        "unit": "seconds",
                        "startValue": 0.0,
                        "endValue": 0.05,
                        "samples": [
                            [0, 1, 2, 3, 4],
                            [0, 1, 2, 5],
                            [0, 1, 2, 3, 4],
                            [],
                            [6],
                        ],
                        "weights": [0.01, 0.01, 0.01, 0.01, 0.01],
                    },
                    {
                        "type": "sampled",
                        "name": "Thread 2",
                        "unit": "seconds",
                        "startValue": 0.0,
                        "endValue": 0.02,
                        "samples": [[5], []],
                        "weights": [0.01, 0.01],
                    },
                ],
                "shared": {
                    "frames": [
                        {
                            "name": "invoke",
                            "file": "/site-packages/click/core.py",
                            "line": 900,
                        },
                        {
                            "name": "_compile_source",
                            "file": "/repo/tools/run_profile.py",
                            "line": 50,
                        },
                        {"name": "compile", "file": "/repo/driver.py", "line": 10},
                        {
                            "name": "parse",
                            "file": "/repo/lark_standalone.py",
                            "line": 20,
                        },
                        {"name": "match", "file": "/usr/regex.py", "line": 30},
                        {"name": "validate", "file": "/repo/validator.py", "line": 40},
                        {
                            "name": "_call_with_frames_removed",
                            "file": "<frozen importlib._bootstrap>",
                            "line": 491,
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_loads_and_aggregates_complete_speedscope_profile(profile_path: Path):
    samples = analyze_profile.load_samples(profile_path)

    assert samples == [
        (
            (
                ("/site-packages/click/core.py", 900, "invoke"),
                ("/repo/tools/run_profile.py", 50, "_compile_source"),
                ("/repo/driver.py", 10, "compile"),
                ("/repo/lark_standalone.py", 20, "parse"),
                ("/usr/regex.py", 30, "match"),
            ),
            0.01,
        ),
        (
            (
                ("/site-packages/click/core.py", 900, "invoke"),
                ("/repo/tools/run_profile.py", 50, "_compile_source"),
                ("/repo/driver.py", 10, "compile"),
                ("/repo/validator.py", 40, "validate"),
            ),
            0.01,
        ),
        (
            (
                ("/site-packages/click/core.py", 900, "invoke"),
                ("/repo/tools/run_profile.py", 50, "_compile_source"),
                ("/repo/driver.py", 10, "compile"),
                ("/repo/lark_standalone.py", 20, "parse"),
                ("/usr/regex.py", 30, "match"),
            ),
            0.01,
        ),
        ((), 0.01),
        (
            (("<frozen importlib._bootstrap>", 491, "_call_with_frames_removed"),),
            0.01,
        ),
        ((("/repo/validator.py", 40, "validate"),), 0.01),
        ((), 0.01),
    ]

    assert analyze_profile.aggregate(samples) == {
        ("/site-packages/click/core.py", 900, "invoke"): (0, 3, 0.0, 0.03),
        ("/repo/tools/run_profile.py", 50, "_compile_source"): (0, 3, 0.0, 0.03),
        ("/repo/driver.py", 10, "compile"): (0, 3, 0.0, 0.03),
        ("/repo/lark_standalone.py", 20, "parse"): (0, 2, 0.0, 0.02),
        ("/usr/regex.py", 30, "match"): (2, 2, 0.02, 0.02),
        ("/repo/validator.py", 40, "validate"): (2, 2, 0.02, 0.02),
        ("<frozen importlib._bootstrap>", 491, "_call_with_frames_removed"): (
            1,
            1,
            0.01,
            0.01,
        ),
    }


def test_removes_complete_excluded_subtree(profile_path: Path):
    samples = analyze_profile.load_samples(profile_path)

    non_lark_samples = analyze_profile.without_file(samples, "lark_standalone.py")

    assert non_lark_samples == [
        (
            (
                ("/site-packages/click/core.py", 900, "invoke"),
                ("/repo/tools/run_profile.py", 50, "_compile_source"),
                ("/repo/driver.py", 10, "compile"),
                ("/repo/validator.py", 40, "validate"),
            ),
            0.01,
        ),
        (
            (("<frozen importlib._bootstrap>", 491, "_call_with_frames_removed"),),
            0.01,
        ),
        ((("/repo/validator.py", 40, "validate"),), 0.01),
    ]


def test_main_reports_samples_without_python_frames(
    profile_path: Path,
):
    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        ["--profile", str(profile_path), "--top", "1"],
    )

    assert result.exit_code == 0
    assert "No Python frame: 0.020s sampled time" in result.output

    samples_with_python_frames = [
        sample for sample in analyze_profile.load_samples(profile_path) if sample[0]
    ]
    with mock.patch.object(
        analyze_profile,
        "load_samples",
        autospec=True,
        return_value=samples_with_python_frames,
    ):
        result = click.testing.CliRunner().invoke(
            analyze_profile.main,
            ["--profile", str(profile_path), "--top", "1"],
        )

    assert result.exit_code == 0
    assert "No Python frame" not in result.output


def test_emit_table_handles_no_sampled_time(capsys: pytest.CaptureFixture[str]):
    analyze_profile.emit_table(
        {("/repo/compiler.py", 1, "compile"): (1, 1, 0.0, 0.0)},
        key="self time",
        n=1,
        title="empty",
        total_time=0.0,
    )

    assert "  0.0%" in capsys.readouterr().out
