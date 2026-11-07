from __future__ import annotations

import re
import shutil
import subprocess
import typing
from pathlib import Path
from unittest import mock

import click.testing
from python.runfiles import runfiles as python_runfiles

from tools import profile_orchestration as run_profile
from tools import runfiles
from tools.profiler import (
    analyzer,
    perf_test_support,
    tachyon_profile,
    tachyon_profiler,
)

if typing.TYPE_CHECKING:
    import pytest

_CONSTRUCTOR_SOURCE = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        define the position<created>.\n"
    "        create a particle in position<created>.\n"
    "    }\n"
    "}\n"
)


def _capture(arguments: list[str]) -> click.testing.Result:
    compiler_path = runfiles.resolve_from_env("COMPILER_BINARY")
    runfiles_resolver = python_runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    target_environment = run_profile._target_environment()  # pyright: ignore[reportPrivateUsage]
    target_environment.update(runfiles_resolver.EnvVars())
    with (
        mock.patch.object(
            run_profile,
            "_build_compiler",
            autospec=True,
            return_value=compiler_path,
        ) as build_compiler,
        mock.patch.object(
            run_profile,
            "_target_environment",
            autospec=True,
            return_value=target_environment,
        ),
    ):
        result = click.testing.CliRunner().invoke(run_profile.main, arguments)
    build_compiler.assert_called_once()
    return result


def _analyze(profile_path: Path) -> str:
    completed = subprocess.run(
        [
            str(runfiles.resolve_from_env("ANALYZER_BINARY")),
            "--profile",
            str(profile_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    in_process = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )
    assert in_process.exit_code == 0
    assert in_process.output == completed.stdout
    return in_process.output


def test_rejects_source_and_project_together(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")

    result = click.testing.CliRunner().invoke(
        run_profile.main,
        [
            "--source",
            str(source_path),
            "--project",
            str(tmp_path),
            "--out",
            str(tmp_path / "profile.jsonl"),
        ],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


def test_requires_source_or_project():
    result = click.testing.CliRunner().invoke(
        run_profile.main,
        ["--out", "profile.jsonl"],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


def test_help_describes_wall_and_cpu_capture_workflow():
    result = click.testing.CliRunner().invoke(
        run_profile.main,
        ["--help"],
        terminal_width=100,
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "Wall mode records all-thread samples with Tachyon" in help_text
    assert "--mode [wall|cpu]" in help_text
    assert "--source" in help_text
    assert "--project" in help_text
    assert "--entry" in help_text
    assert "--max-threads" in help_text
    assert "--output-dir" in help_text


def test_changes_to_build_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    invocation_directory = tmp_path / "runfiles"
    invocation_directory.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(invocation_directory)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(workspace))

    run_profile.chdir_to_build_workspace()

    assert Path.cwd() == workspace


def test_keeps_working_directory_outside_bazel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BUILD_WORKSPACE_DIRECTORY", raising=False)

    run_profile.chdir_to_build_workspace()

    assert Path.cwd() == tmp_path


def test_builds_compiler_before_preparing_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    completed_build = subprocess.CompletedProcess[str]([], 0)

    # Bazel cannot invoke its own persistent server from a running Bazel test.
    with (
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            return_value="/usr/bin/bazelisk",
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=completed_build,
        ) as subprocess_run,
        mock.patch.object(
            tachyon_profiler,
            "capture",
            autospec=True,
            return_value=0,
        ) as capture,
        mock.patch.object(
            tachyon_profile,
            "load",
            autospec=True,
            return_value=tachyon_profile.WallProfile(
                python_version="3.15.2",
                sample_interval_ns=1_000_000,
                failed_sample_percent=0.5,
                main_thread_id=1,
                started_ns=0,
                ended_ns=2_000_000_000,
                frames=[],
                observation_count=1,
                samples_by_thread={1: []},
            ),
        ),
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(tmp_path / "profile.bin"),
            ],
        )

    assert result.exit_code == 0
    output_lines = result.output.splitlines()
    assert output_lines[0] == "Building the compiler with --config=profiling"
    assert output_lines[1].startswith("Generated code directory: ")
    assert output_lines[2:] == [
        f"Profile: {tmp_path / 'profile.bin'}",
        "Capture: compiler exit 0",
        "Samples: 2.00 s of wall time; 1 threads; failed samples 0.5%",
        "Generated code: 0 files; 0.0 MB",
    ]
    subprocess_run.assert_called_once_with(
        [
            "/usr/bin/bazelisk",
            "build",
            "--config=profiling",
            "--build_runfile_links",
            "--noshow_progress",
            "--ui_event_filters=-info",
            "//define/compiler:main",
        ],
        check=True,
        cwd=tmp_path,
    )
    capture.assert_called_once()
    assert capture.call_args.kwargs["command"][0] == str(
        tmp_path / "bazel-bin/define/compiler/main"
    )
    assert capture.call_args.kwargs["working_directory"] == tmp_path


def test_profiles_source_through_public_profiler_and_analyzer(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")
    profile_path = tmp_path / "source-profile.bin"

    result = _capture(
        [
            "--source",
            str(source_path),
            "--out",
            str(profile_path),
            "--max-threads",
            "3",
        ]
    )

    assert result.exit_code == 0
    assert re.search(
        r"^Samples: \d+\.\d\d s of wall time; \d+ threads; failed samples ",
        result.output,
        re.MULTILINE,
    )
    profile = tachyon_profile.load(profile_path)
    assert profile.observation_count > 0
    analysis = _analyze(profile_path)
    assert "Profile: Tachyon wall samples" in analysis
    assert " (main): " in analysis


def test_profiles_project_entry_through_public_profiler_and_analyzer(tmp_path: Path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = project_path / ".define/project/config.defcl"
    config_path.parent.mkdir(parents=True)
    _ = config_path.write_text(
        'project: { universe_name: "my.domain.com:my_lib" }\n',
        encoding="utf-8",
        newline="\n",
    )
    entry_path = project_path / "main.dfn"
    _ = entry_path.write_text(
        _CONSTRUCTOR_SOURCE.replace(":/test>", ":/main>"),
        encoding="utf-8",
        newline="\n",
    )
    profile_path = tmp_path / "project-profile.bin"
    output_dir = tmp_path / "generated"

    result = _capture(
        [
            "--project",
            str(project_path),
            "--entry",
            "main.dfn",
            "--out",
            str(profile_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result.exit_code == 0
    assert output_dir.is_dir()
    generated_count = sum(1 for path in output_dir.rglob("*") if path.is_file())
    assert f"Generated code: {generated_count} files; " in result.output
    profile = tachyon_profile.load(profile_path)
    assert profile.observation_count > 0
    analysis = _analyze(profile_path)
    assert "Profile: Tachyon wall samples" in analysis
    assert " (main): " in analysis


def test_profiles_cpu_through_public_profiler(tmp_path: Path):
    perf_test_support.require_perf_recording(tmp_path)
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")
    profile_path = tmp_path / "stacks.txt"

    result = _capture(
        [
            "--mode",
            "cpu",
            "--source",
            str(source_path),
            "--out",
            str(profile_path),
            "--max-threads",
            "3",
        ]
    )

    assert result.exit_code == 0
    assert re.search(
        r"^Samples: \d+\.\d\d s of CPU time; \d+ threads; stacks not unwound "
        + r"\d+\.\d%$",
        result.output,
        re.MULTILINE,
    )
    assert "/define/compiler/" in profile_path.read_text(encoding="utf-8")
