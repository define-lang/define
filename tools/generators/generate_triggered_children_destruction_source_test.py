from __future__ import annotations

from typing import TYPE_CHECKING

import click.testing
import pytest

from define.compiler import driver
from define.compiler.errors import diagnostics
from tools.generators import generate_triggered_children_destruction_source as gen

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("shape", "additional_actions", "additional_positions"),
    [
        (gen.Shape.LOCAL, 1, 0),
        (gen.Shape.DESTRUCTORS, 2, 0),
        (gen.Shape.CONTRACTED, 2, 0),
        (gen.Shape.MOVE, 2, 0),
        (gen.Shape.REARRANGE, 2, 4),
        (gen.Shape.REARRANGE_DESTRUCTORS, 3, 4),
        (gen.Shape.DEPENDENT_SIBLINGS, 4, 1),
    ],
)
@pytest.mark.parametrize(("depth", "fan_out"), [(1, 1), (1, 3), (4, 1), (4, 2)])
def test_valid_program(
    shape: gen.Shape,
    additional_actions: int,
    additional_positions: int,
    depth: int,
    fan_out: int,
    tmp_path: Path,
):
    source = "\n".join(gen.generate_source_lines(depth, fan_out, shape)) + "\n"
    result = driver.Driver().compile_source(source, tmp_path / "generated")
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    assert source.count("define the potential action<") == depth + additional_actions
    assert (
        source.count("define the potential position<")
        == (depth - 1) * fan_out + additional_positions
    )
    assert source.count("::action</fill_") == (depth - 1) * fan_out + 1


def test_error_program_reports_its_one_error(tmp_path: Path):
    source = "\n".join(gen.generate_source_lines(4, 2, gen.Shape.ERROR)) + "\n"
    result = driver.Driver().compile_source(source, tmp_path / "generated")
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 13
    assert diagnostic.location.end_column == 66
    assert diagnostic.position_name == "position<scratch>::position</detail>"
    assert diagnostic.parent_position_name == "position<scratch>"


@pytest.mark.parametrize(("depth", "fan_out"), [(0, 1), (1, 0)])
def test_invalid_sizes(depth: int, fan_out: int):
    with pytest.raises(ValueError, match="must be"):
        _ = gen.generate_source_lines(depth, fan_out)


def test_cli(tmp_path: Path):
    output = tmp_path / "destruction.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--depth",
            "3",
            "--fan-out",
            "2",
            "--shape",
            "move",
            "--fqun-prefix",
            "mv:example.com:generated",
        ],
    )
    assert result.exit_code == 0
    assert (
        output.read_text()
        == "\n".join(
            gen.generate_source_lines(3, 2, gen.Shape.MOVE, "mv:example.com:generated")
        )
        + "\n"
    )
