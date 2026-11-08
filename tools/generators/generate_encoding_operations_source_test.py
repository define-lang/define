from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click import testing

from define.compiler import driver
from tools.generators import generate_encoding_operations_source as gen

if TYPE_CHECKING:
    from pathlib import Path


def _source(*, view_settings: bool) -> str:
    return (
        "\n".join(
            gen.generate_source_lines(
                operations=5, statements=4, chain_depth=3, view_settings=view_settings
            )
        )
        + "\n"
    )


@pytest.mark.parametrize("view_settings", [False, True])
def test_generated_source_compiles(tmp_path: Path, *, view_settings: bool):
    source = _source(view_settings=view_settings)

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []


def test_single_statement_operations_compile(tmp_path: Path):
    source = (
        "\n".join(gen.generate_source_lines(operations=2, statements=1, chain_depth=2))
        + "\n"
    )

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []
    assert "define the view<step_" not in source


def test_output_shape():
    source = _source(view_settings=True)

    assert source.count("define the encoding_operation<") == 5
    assert source.count("execute the encoding_operation</encoding/operation_") == 3
    assert "execute the encoding_operation</encoding/operation_2>" not in source
    assert "execute the encoding_operation</encoding/operation_3>" in source
    assert source.count("set the value of view<copy_") == 5 * 2
    assert "set the value of view<copy_1> from view<step_1>." in source
    assert 'with view<b> looking at literal<standard:/number>"3".' in source


def test_without_view_settings_every_add_takes_a_literal():
    source = _source(view_settings=False)

    assert "set the value of" not in source
    assert source.count("looking at literal<standard:/number>") == 5 * 4 - 3


@pytest.mark.parametrize(
    ("operations", "statements", "chain_depth", "message"),
    [
        (0, 1, 1, "operations must be at least 1"),
        (1, 0, 1, "statements must be at least 1"),
        (1, 1, 0, "chain_depth must be at least 1"),
    ],
)
def test_rejects_invalid_sizes(
    operations: int, statements: int, chain_depth: int, message: str
):
    with pytest.raises(ValueError, match=message):
        _ = gen.generate_source_lines(
            operations=operations, statements=statements, chain_depth=chain_depth
        )


def test_cli_writes_source(tmp_path: Path):
    output = tmp_path / "generated.dfn"

    result = testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--operations",
            "5",
            "--statements",
            "4",
            "--chain-depth",
            "3",
            "--no-view-settings",
        ],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8") == _source(view_settings=False)
