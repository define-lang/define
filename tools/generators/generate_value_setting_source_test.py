from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click import testing

from define.compiler import driver
from tools.generators import generate_value_setting_source as gen

if TYPE_CHECKING:
    from pathlib import Path


def _source(*, binary_values: bool) -> str:
    return (
        "\n".join(
            gen.generate_source_lines(
                positions=3,
                qualities_per_position=2,
                statements=7,
                literal_digits=12,
                binary_values=binary_values,
            )
        )
        + "\n"
    )


@pytest.mark.parametrize("binary_values", [False, True])
def test_generated_source_compiles(tmp_path: Path, *, binary_values: bool):
    source = _source(binary_values=binary_values)

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []


def test_output_shape():
    source = _source(binary_values=False)

    assert source.count("it has the position</extra_") == 3 * 2
    assert source.count("execute the operation<standard:/number/natural/add>") == 4
    assert source.count("set the value of position</value_") == 1 + 3
    assert (
        'set the value of position</value_0> from literal<standard:/number>"101234567890".'
        in source
    )
    assert 'with view<b> looking at literal<standard:/number>"301234567890".' in source
    assert "set the value of position</value_2> from position</value_1>." in source
    assert "with view<result> looking at position</value_0>." in source


def test_binary_values_use_binary_operations():
    source = _source(binary_values=True)

    assert "it has the value<standard:/binary>." in source
    assert source.count("execute the operation<standard:/binary/or>") == 4


@pytest.mark.parametrize(
    ("positions", "qualities_per_position", "statements", "literal_digits", "message"),
    [
        (1, 0, 1, 1, "positions must be at least 2"),
        (2, -1, 1, 1, "qualities_per_position must not be negative"),
        (2, 0, 0, 1, "statements must be at least 1"),
        (2, 0, 1, 0, "literal_digits must be at least 1"),
    ],
)
def test_rejects_invalid_sizes(
    positions: int,
    qualities_per_position: int,
    statements: int,
    literal_digits: int,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        _ = gen.generate_source_lines(
            positions=positions,
            qualities_per_position=qualities_per_position,
            statements=statements,
            literal_digits=literal_digits,
        )


def test_cli_writes_source(tmp_path: Path):
    output = tmp_path / "generated.dfn"

    result = testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--positions",
            "3",
            "--qualities-per-position",
            "2",
            "--statements",
            "7",
            "--literal-digits",
            "12",
            "--binary-values",
        ],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8") == _source(binary_values=True)


def test_cli_rejects_binary_literals_too_long_to_convert(tmp_path: Path):
    result = testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(tmp_path / "generated.dfn"),
            "--literal-digits",
            str(gen.MAX_BINARY_LITERAL_DIGITS + 1),
            "--binary-values",
        ],
    )

    assert result.exit_code == 2
    assert "literal_digits must be at most 4300 with binary values" in result.output
