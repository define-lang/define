from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import click.testing
import pytest

from define.compiler import diagnostics, driver, parser
from tools.generators import generate_diagnostics_source as gen

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(("count", "name_length", "padding"), [(1, 1, 0), (3, 100, 20)])
def test_exact_diagnostics_and_formatting(count: int, name_length: int, padding: int):
    source = "\n".join(gen.generate_source_lines(count, name_length, padding)) + "\n"
    result = driver.Driver().validate_source(source)
    assert result.program_validation.all_exceptions == []
    all_diagnostics = result.program_validation.all_diagnostics
    assert [type(diagnostic) for diagnostic in all_diagnostics] == [
        diagnostics.CreateInOccupiedPositionDiagnostic
    ] * count
    assert [diagnostic.location.line for diagnostic in all_diagnostics] == list(
        range(padding + 7, padding + 7 + 3 * count, 3)
    )
    formatted = result.error_strings()
    assert len(formatted) == count
    for index, message in enumerate(formatted):
        assert f"value_{index}".ljust(name_length, "x") in message


@pytest.mark.parametrize(
    ("count", "name_length", "padding"), [(0, 1, 0), (1, 0, 0), (1, 1, -1)]
)
def test_invalid_sizes(count: int, name_length: int, padding: int):
    with pytest.raises(ValueError, match="must be at least"):
        _ = gen.generate_source_lines(count, name_length, padding)


def test_cli(tmp_path: Path):
    output = tmp_path / "diagnostics.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--errors",
            "2",
            "--name-length",
            "50",
            "--padding-lines",
            "5",
            "--fqun-prefix",
            "mv:example.com:generated",
        ],
    )
    assert result.exit_code == 0
    assert (
        output.read_text()
        == "\n".join(gen.generate_source_lines(2, 50, 5, "mv:example.com:generated"))
        + "\n"
    )


@pytest.mark.parametrize("width", [1, 1000])
def test_indentation_diagnostics(width: int):
    source = "\n".join(gen.generate_source_lines(errors=2, indent_width=width)) + "\n"
    result = parser.Parser().parse_and_transform(
        source, file_path=PurePosixPath("test.dfn")
    )
    assert result.exception is None
    assert [type(diagnostic) for diagnostic in result.diagnostics] == [
        diagnostics.IncorrectIndentationDiagnostic
    ] * 8


def test_invalid_indentation_width():
    with pytest.raises(ValueError, match="indent_width"):
        _ = gen.generate_source_lines(indent_width=0)


def test_indentation_cli(tmp_path: Path):
    output = tmp_path / "indentation.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main, ["--output", str(output), "--errors", "1", "--indent-width", "100"]
    )
    assert result.exit_code == 0
    assert (
        output.read_text()
        == "\n".join(gen.generate_source_lines(errors=1, indent_width=100)) + "\n"
    )
