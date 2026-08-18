import json
import os
import shutil
import subprocess
import typing
from pathlib import Path
from unittest import mock

import click.testing
import pytest
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools import profile_orchestration as run_profile
from tools.profiler import analyzer, perf_analyzer, perf_test_support, schema

# PRF-041: Realistic tests.
_CONSTRUCTOR_SOURCE = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    define the position<created>.\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        create a particle in position<created>.\n"
    "    }\n"
    "}\n"
)


def _runfile(variable: str) -> Path:
    # PRF-041: Realistic tests.
    location = Path(os.environ[variable])
    if location.exists():
        return location
    runfiles_resolver = runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    resolved = runfiles_resolver.Rlocation(str(location))
    assert resolved is not None
    return Path(resolved)


def _capture(arguments: list[str]) -> click.testing.Result:
    # PRF-012: Orchestration boundary. PRF-041: Realistic tests.
    compiler_path = _runfile("COMPILER_BINARY")
    runfiles_resolver = runfiles.Runfiles.Create()
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
    # PRF-020: Machine and human interfaces. PRF-043: Analyzer at every checkpoint.
    completed = subprocess.run(
        [str(_runfile("ANALYZER_BINARY")), "--profile", str(profile_path)],
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


# PRF-012: Orchestration boundary.
def test_rejects_source_and_project_together(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")

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


# PRF-012: Orchestration boundary.
def test_requires_source_or_project():
    result = click.testing.CliRunner().invoke(
        run_profile.main,
        ["--out", "profile.jsonl"],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


# PRF-012: Orchestration boundary. PRF-020: Machine and human interfaces.
def test_help_describes_wall_and_cpu_capture_workflow():
    result = click.testing.CliRunner().invoke(
        run_profile.main,
        ["--help"],
        terminal_width=100,
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "wall observations or Linux perf CPU samples" in help_text
    assert "--mode [wall|cpu]" in help_text
    assert "--source" in help_text
    assert "--project" in help_text
    assert "--entry" in help_text
    assert "--max-threads" in help_text
    assert "--output-dir" in help_text


# PRF-012: Orchestration boundary.
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


# PRF-012: Orchestration boundary.
def test_keeps_working_directory_outside_bazel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BUILD_WORKSPACE_DIRECTORY", raising=False)

    run_profile.chdir_to_build_workspace()

    assert Path.cwd() == tmp_path


# PRF-012: Orchestration boundary.
def test_builds_compiler_before_preparing_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
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
            run_profile,
            "record_profile",
            autospec=True,
        ) as record_profile,
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(tmp_path / "profile.jsonl"),
            ],
        )

    assert result.exit_code == 0
    subprocess_run.assert_called_once_with(
        [
            "/usr/bin/bazelisk",
            "build",
            "--noshow_progress",
            "--ui_event_filters=-info",
            "//define/compiler:main",
        ],
        check=True,
        cwd=tmp_path,
    )
    record_profile.assert_called_once()
    invocation = typing.cast(
        "run_profile.ProfileInvocation",
        record_profile.call_args.args[0],
    )
    assert invocation.profiler_working_directory == tmp_path
    assert invocation.profiler_arguments == ("--mode", "wall")
    assert invocation.target_command[0] == str(
        tmp_path / "bazel-bin/define/compiler/main"
    )


# PRF-011: Complete invocation. PRF-012: Orchestration boundary.
# PRF-025: Failure threshold. PRF-026: No silent partial success.
# PRF-020: Machine and human interfaces. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_profiles_source_through_public_profiler_and_analyzer(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "source-profile.jsonl"

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

    profile = schema.load(profile_path)
    assert result.exit_code == (0 if profile.success else 1)
    assert profile.complete is True
    assert profile.compiler_exit_status == 0
    assert profile.diagnostics_status == "none"
    assert profile.failures == []
    assert profile.sampling_statistics is not None
    assert profile.success is (profile.discarded_rate <= 0.001)
    assert profile.workload_path == str(source_path)
    workspace = Path(run_profile.__file__).resolve().parent.parent
    assert profile.working_directory == str(workspace)
    assert profile.command[1:6] == [
        "compile",
        "--out",
        profile.command[3],
        "--max-threads",
        "3",
    ]
    assert not Path(profile.command[3]).exists()
    analysis = _analyze(profile_path)
    capture_status = "successful" if profile.success else "unsuccessful"
    assert (
        f"Profile schema: {schema.SCHEMA_VERSION}; complete; {capture_status}"
        in analysis
    )
    assert "Self wall occupancy (union across threads):" in analysis


# PRF-011: Complete invocation. PRF-012: Orchestration boundary.
# PRF-025: Failure threshold. PRF-026: No silent partial success.
# PRF-020: Machine and human interfaces. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_profiles_project_entry_through_public_profiler_and_analyzer(tmp_path: Path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = project_path / ".define/project/config.defcl"
    config_path.parent.mkdir(parents=True)
    _ = config_path.write_text(
        'project: { universe_name: "my.domain.com:my_lib" }\n',
        encoding="utf-8",
    )
    entry_path = project_path / "main.dfn"
    _ = entry_path.write_text(
        _CONSTRUCTOR_SOURCE.replace(":/test>", ":/main>"),
        encoding="utf-8",
    )
    profile_path = tmp_path / "project-profile.jsonl"
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

    profile = schema.load(profile_path)
    assert result.exit_code == (0 if profile.success else 1)
    assert profile.complete is True
    assert profile.compiler_exit_status == 0
    assert profile.diagnostics_status == "none"
    assert profile.failures == []
    assert profile.sampling_statistics is not None
    assert profile.success is (profile.discarded_rate <= 0.001)
    assert profile.workload_path == str(entry_path)
    assert profile.working_directory == str(project_path)
    assert profile.command[-1] == str(entry_path)
    assert profile.command[profile.command.index("--out") + 1] == str(output_dir)
    assert output_dir.is_dir()
    analysis = _analyze(profile_path)
    capture_status = "successful" if profile.success else "unsuccessful"
    assert (
        f"Profile schema: {schema.SCHEMA_VERSION}; complete; {capture_status}"
        in analysis
    )
    assert "Cumulative wall occupancy (union across threads):" in analysis


# PRF-011: Complete invocation. PRF-012: Orchestration boundary.
# PRF-014: CPU mode. PRF-020: Machine and human interfaces.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_profiles_cpu_through_public_profiler_and_analyzer(tmp_path: Path):
    perf_test_support.require_perf_recording(tmp_path)
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "perf.data"

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

    profile = perf_analyzer.load(profile_path)
    assert result.exit_code == (0 if profile.success else 1)
    assert profile.metadata["compiler_exit_status"] == 0
    assert profile.diagnostics == ""
    assert profile.event == "cpu-clock"
    assert profile_path.read_bytes().startswith(b"PERFILE2")
    assert (
        json.loads(
            profile_path.with_name(profile_path.name + ".json").read_text(
                encoding="utf-8"
            )
        )
        == profile.metadata
    )
    analysis = _analyze(profile_path)
    capture_status = "successful" if profile.success else "unsuccessful"
    assert f"Native perf profile: complete; {capture_status}" in analysis
    assert "CPU backend: linux-perf" in analysis
    assert "Self CPU attribution:" in analysis
    assert "Cumulative CPU attribution:" in analysis
