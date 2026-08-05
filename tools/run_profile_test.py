import cProfile
from pathlib import Path
from unittest import mock

import click.testing
import pytest

from define.compiler import driver
from tools import run_profile
from tools.generators import generate_reference_graph_project

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


def test_profiles_source_through_driver(tmp_path: Path):
    source_path = tmp_path / "source.dfn"
    _ = source_path.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8")
    profile_path = tmp_path / "source.prof"

    original_compile_source = driver.Driver.compile_source
    with (
        mock.patch.object(cProfile, "Profile", autospec=True),
        mock.patch.object(
            driver.Driver,
            "compile_source",
            autospec=True,
            side_effect=original_compile_source,
        ) as compile_source,
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
    assert compile_source.call_args.kwargs["max_threads"] == 3
    assert result.output == (
        f"has_errors=False\nprofile written to {profile_path.absolute()}\n"
    )


def test_profiles_project_through_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_path = tmp_path / "project"
    files = generate_reference_graph_project.generate_project_files(modules=4, layers=2)
    generate_reference_graph_project.write_project(project_path, files)
    profile_path = tmp_path / "project.prof"
    output_dir = tmp_path / "generated"
    monkeypatch.chdir(tmp_path)

    with mock.patch.object(cProfile, "Profile", autospec=True):
        result = click.testing.CliRunner().invoke(
            run_profile.main,
            [
                "--project",
                str(project_path),
                "--out",
                str(profile_path),
                "--output-dir",
                str(output_dir),
            ],
        )

    assert result.exit_code == 0
    assert result.output == (
        f"has_errors=False\nprofile written to {profile_path.absolute()}\n"
    )
    assert (output_dir / "__main__.py").is_file()


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
            str(tmp_path / "profile.prof"),
        ],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output


def test_requires_source_or_project(tmp_path: Path):
    result = click.testing.CliRunner().invoke(
        run_profile.main,
        ["--out", str(tmp_path / "profile.prof")],
    )

    assert result.exit_code == 2
    assert "Error: provide exactly one of --source or --project" in result.output
