from pathlib import Path

import pytest
from click import testing

from define.compiler import driver
from tools.generators import generate_action_plan_source


def test_generated_source_compiles(tmp_path: Path):
    source = (
        "\n".join(
            generate_action_plan_source.generate_source_lines(
                actions=3,
                chains_per_action=4,
                topology_groups=3,
                topology_width=4,
                fqun_prefix="mv:define-lang.org:test",
            )
        )
        + "\n"
    )

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []


def test_cli_writes_source(tmp_path: Path):
    output = tmp_path / "generated.dfn"

    result = testing.CliRunner().invoke(
        generate_action_plan_source.main,
        [
            "--output",
            str(output),
            "--actions",
            "2",
            "--chains-per-action",
            "3",
            "--topology-groups",
            "2",
            "--topology-width",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert output.is_file()


@pytest.mark.parametrize("option", ["--actions", "--topology-groups"])
def test_cli_allows_omitting_a_shape(tmp_path: Path, option: str):
    output = tmp_path / f"{option[2:]}.dfn"

    result = testing.CliRunner().invoke(
        generate_action_plan_source.main,
        ["--output", str(output), option, "0"],
    )

    assert result.exit_code == 0
