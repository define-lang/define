import json
import shutil
import subprocess
import typing
from pathlib import Path
from unittest import mock

import click.testing

from tools import run_profile

if typing.TYPE_CHECKING:
    import io

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
_RAW_SAMPLES = "Driver.run (/repo/define/compiler/driver.py:234) 1\n"
_WALL_EVENTS = [
    {
        "args": {"filename": "/repo/define/compiler/driver.py", "line": 234},
        "cat": "py-spy",
        "name": "Driver.run",
        "ph": "B",
        "pid": 1,
        "tid": 1,
        "ts": 1_000,
    },
    {
        "args": {"filename": "/repo/define/compiler/driver.py", "line": 234},
        "cat": "py-spy",
        "name": "Driver.run",
        "ph": "E",
        "pid": 1,
        "tid": 1,
        "ts": 11_000,
    },
]


def _executable_path(executable: str) -> str:
    return f"/usr/bin/{executable}"


def _profile_process(
    command: list[str], *, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    if "--output" in command:
        output_option = command.index("--output")
        profile_path = Path(command[output_option + 1])
        format_option = command.index("--format")
        profile_format = command[format_option + 1]
        profile_contents = (
            json.dumps(_WALL_EVENTS)
            if profile_format == "chrometrace"
            else _RAW_SAMPLES
        )
        _ = profile_path.write_text(profile_contents, encoding="utf-8")
    return subprocess.CompletedProcess[str](command, returncode)


def _successful_profile_process(
    command: list[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    return _profile_process(command)


def _failed_profile_process(
    command: list[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    if Path(command[0]).name != "py-spy":
        return subprocess.CompletedProcess[str](command, 0)
    return _profile_process(command, returncode=1)


def _failed_profile_process_without_output(
    command: list[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess[str](
        command, 1 if Path(command[0]).name == "py-spy" else 0
    )


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
            str(tmp_path / "profile.json"),
        ],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


def test_requires_source_or_project():
    result = click.testing.CliRunner().invoke(
        run_profile.main, ["--out", "profile.json"]
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


def test_help_explains_capture_modes():
    result = click.testing.CliRunner().invoke(
        run_profile.main, ["--help"], terminal_width=100
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "The profile mode must match the mode later passed to analyze_profile." in (
        help_text
    )
    assert "Wall mode records idle time and all Python threads" in help_text
    assert "CPU mode records active work across Python threads" in help_text
    assert "CPU mode records active raw samples" in help_text


def test_invokes_py_spy_on_compiler_main(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "profile.json"

    with (
        mock.patch.dict(
            "os.environ",
            {
                "BUILD_WORKSPACE_DIRECTORY": "/repo",
                "RUNFILES_DIR": "/repo/bazel-bin/tools/run_profile.runfiles",
                "VIRTUAL_ENV": "/repo/bazel-bin/tools/.run_profile.venv",
            },
            clear=False,
        ),
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            side_effect=_executable_path,
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=_successful_profile_process,
        ) as subprocess_run,
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(profile_path),
                "--max-threads",
                "3",
            ],
        )

    assert result.exit_code == 0
    assert result.output == ""
    assert subprocess_run.call_count == 2
    build_call, profile_call = subprocess_run.call_args_list
    assert build_call.args[0] == [
        "/usr/bin/bazelisk",
        "build",
        "--noshow_progress",
        "--ui_event_filters=-info",
        "//define/compiler:main",
    ]
    assert build_call.kwargs == {"check": True, "cwd": Path("/repo")}
    command = typing.cast("list[str]", profile_call.args[0])
    compiler_output_dir = Path(command[command.index("--out") + 1])
    assert compiler_output_dir.name.startswith("cg_profile_")
    assert not compiler_output_dir.exists()
    assert command == [
        "/usr/bin/py-spy",
        "record",
        "--format",
        "chrometrace",
        "--full-filenames",
        "--idle",
        "--output",
        str(profile_path),
        "--",
        "/repo/bazel-bin/define/compiler/main",
        "compile",
        "--out",
        str(compiler_output_dir),
        "--max-threads",
        "3",
    ]
    assert json.loads(profile_path.read_text(encoding="utf-8")) == _WALL_EVENTS
    assert profile_call.kwargs["check"] is False
    assert profile_call.kwargs["cwd"] == Path("/repo")
    source_stream = typing.cast("io.BufferedReader", profile_call.kwargs["stdin"])
    assert Path(source_stream.name) == source_path
    assert source_stream.closed
    environment = typing.cast("dict[str, str]", profile_call.kwargs["env"])
    assert "RUNFILES_DIR" not in environment
    assert "VIRTUAL_ENV" not in environment


def test_uses_project_entry_as_compiler_input(tmp_path: Path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    entry_path = project_path / "main.dfn"
    _ = entry_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    output_dir = tmp_path / "generated"

    with (
        mock.patch.dict("os.environ", {}, clear=True),
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            side_effect=_executable_path,
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=_successful_profile_process,
        ) as subprocess_run,
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--project",
                str(project_path),
                "--entry",
                "main.dfn",
                "--out",
                str(profile_path),
                "--output-dir",
                str(output_dir),
            ],
        )

    assert result.exit_code == 0
    assert subprocess_run.call_count == 2
    build_call, profile_call = subprocess_run.call_args_list
    expected_workspace = Path(run_profile.__file__).resolve().parent.parent
    assert build_call.kwargs["cwd"] == expected_workspace
    command = typing.cast("list[str]", profile_call.args[0])
    assert command == [
        "/usr/bin/py-spy",
        "record",
        "--format",
        "chrometrace",
        "--full-filenames",
        "--idle",
        "--output",
        str(profile_path),
        "--",
        str(expected_workspace / "bazel-bin/define/compiler/main"),
        "compile",
        "--out",
        str(output_dir),
        "--max-threads",
        "1",
        str(entry_path),
    ]
    assert profile_call.kwargs["cwd"] == project_path
    assert profile_call.kwargs["stdin"] is None


def test_cpu_profile_records_all_active_threads(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")

    with (
        mock.patch.dict("os.environ", {}, clear=True),
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            side_effect=_executable_path,
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=_successful_profile_process,
        ) as subprocess_run,
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(tmp_path / "profile.json"),
                "--max-threads",
                "4",
                "--profile-mode",
                "cpu",
            ],
        )

    assert result.exit_code == 0
    build_command = typing.cast("list[str]", subprocess_run.call_args_list[0].args[0])
    assert build_command[-1] == "//define/compiler:main"
    command = typing.cast("list[str]", subprocess_run.call_args_list[1].args[0])
    assert "--python" not in command
    assert "--gil" not in command
    assert "--idle" not in command
    workspace = Path(run_profile.__file__).resolve().parent.parent
    raw_output_path = Path(command[command.index("--output") + 1])
    assert raw_output_path.name == "samples.txt"
    assert raw_output_path.parent.name.startswith("define_profile_")
    assert not raw_output_path.exists()
    compiler_output_dir = Path(command[command.index("--out") + 1])
    assert compiler_output_dir.name.startswith("cg_profile_")
    assert not compiler_output_dir.exists()
    assert command == [
        "/usr/bin/py-spy",
        "record",
        "--format",
        "raw",
        "--full-filenames",
        "--output",
        str(raw_output_path),
        "--",
        str(workspace / "bazel-bin/define/compiler/main"),
        "compile",
        "--out",
        str(compiler_output_dir),
        "--max-threads",
        "4",
    ]
    profile = typing.cast(
        "dict[str, object]",
        json.loads((tmp_path / "profile.json").read_text(encoding="utf-8")),
    )
    assert profile.keys() == {"wall_time_seconds", "raw_samples"}
    assert profile["raw_samples"] == _RAW_SAMPLES
    assert isinstance(profile["wall_time_seconds"], float)
    assert profile["wall_time_seconds"] >= 0.0


def test_cpu_profile_preserves_raw_samples_when_py_spy_fails(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "profile.json"

    with (
        mock.patch.dict("os.environ", {}, clear=True),
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            side_effect=_executable_path,
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=_failed_profile_process,
        ),
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(profile_path),
                "--profile-mode",
                "cpu",
            ],
        )

    assert result.exit_code == 1
    assert isinstance(result.exception, subprocess.CalledProcessError)
    assert result.exception.returncode == 1
    profile = typing.cast(
        "dict[str, object]", json.loads(profile_path.read_text(encoding="utf-8"))
    )
    assert profile.keys() == {"wall_time_seconds", "raw_samples"}
    assert profile["raw_samples"] == _RAW_SAMPLES
    assert isinstance(profile["wall_time_seconds"], float)
    assert profile["wall_time_seconds"] >= 0.0


def test_cpu_profile_propagates_py_spy_failure_without_profile(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "profile.json"

    with (
        mock.patch.dict("os.environ", {}, clear=True),
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            side_effect=_executable_path,
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=_failed_profile_process_without_output,
        ),
    ):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--source",
                str(source_path),
                "--out",
                str(profile_path),
                "--profile-mode",
                "cpu",
            ],
        )

    assert result.exit_code == 1
    assert isinstance(result.exception, subprocess.CalledProcessError)
    assert result.exception.returncode == 1
    assert not profile_path.exists()
