from __future__ import annotations

from typing import TYPE_CHECKING

import click.testing
import pytest

from define.compiler import driver
from tools.generators import generate_quality_implications_source as gen

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("layers", "width", "fan_out"), [(1, 1, 1), (6, 1, 1), (3, 3, 2), (3, 2, 2)]
)
def test_valid_implication_graph(layers: int, width: int, fan_out: int, tmp_path: Path):
    source = "\n".join(gen.generate_source_lines(layers, width, fan_out, 2)) + "\n"
    result = driver.Driver().compile_source(source, tmp_path / "generated")
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    assert source.count("it also assigns the") == (layers - 1) * width * fan_out
    assert source.count("define the potential action<") == layers * width + 1
    assert source.count("        create a particle in position<sample_") == 2 * (
        width + 1
    )


@pytest.mark.parametrize(
    ("layers", "width", "fan_out", "assignments"),
    [(0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 0), (1, 1, 0, 1), (1, 1, 2, 1)],
)
def test_invalid_sizes(layers: int, width: int, fan_out: int, assignments: int):
    with pytest.raises(ValueError, match="must be"):
        _ = gen.generate_source_lines(layers, width, fan_out, assignments)


def test_cli(tmp_path: Path):
    output = tmp_path / "implications.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--layers",
            "3",
            "--width",
            "1",
            "--fan-out",
            "1",
            "--assignments",
            "2",
            "--fqun-prefix",
            "mv:example.com:generated",
        ],
    )
    assert result.exit_code == 0
    assert (
        output.read_text()
        == "\n".join(gen.generate_source_lines(3, 1, 1, 2, "mv:example.com:generated"))
        + "\n"
    )
