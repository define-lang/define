from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click import testing

from define.compiler import driver
from tools.generators import generate_wide_value_operations_source as gen

if TYPE_CHECKING:
    from pathlib import Path


def _source(views: int, executions: int, operation_callers: int) -> str:
    return (
        "\n".join(
            gen.generate_source_lines(
                views=views, executions=executions, operation_callers=operation_callers
            )
        )
        + "\n"
    )


def test_generated_source_compiles(tmp_path: Path):
    source = _source(views=4, executions=5, operation_callers=2)

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []


def test_two_views_write_the_result_directly(tmp_path: Path):
    source = _source(views=2, executions=1, operation_callers=0)

    result = driver.Driver().compile_source(source, tmp_path / "generated")

    assert result.error_strings() == []
    assert "define the view<product_" not in source


def test_output_shape():
    source = _source(views=4, executions=5, operation_callers=2)

    assert source.count("define the operation<") == 3
    assert source.count("execute the logical_operation<") == 3
    assert source.count("execute the operation</product>") == 2 + 2
    assert source.count("execute the operation</caller_0>") == 2
    assert source.count("execute the operation</caller_1>") == 1
    assert source.count("define the position<result_") == 4
    assert (
        "with view<a_0> looking at position<result_3>.\n"
        "            with view<a_1> looking at position<input_1>."
    ) in source
    assert "with view<result> looking at position</total>." in source


@pytest.mark.parametrize(
    ("views", "executions", "operation_callers", "message"),
    [
        (1, 1, 0, "views must be at least 2"),
        (2, 0, 0, "executions must be at least 1"),
        (2, 1, -1, "operation_callers must not be negative"),
    ],
)
def test_rejects_invalid_sizes(
    views: int, executions: int, operation_callers: int, message: str
):
    with pytest.raises(ValueError, match=message):
        _ = gen.generate_source_lines(
            views=views, executions=executions, operation_callers=operation_callers
        )


def test_cli_writes_source(tmp_path: Path):
    output = tmp_path / "generated.dfn"

    result = testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--views",
            "3",
            "--executions",
            "2",
            "--operation-callers",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8") == _source(
        views=3, executions=2, operation_callers=1
    )


def test_cli_rejects_one_view(tmp_path: Path):
    result = testing.CliRunner().invoke(
        gen.main, ["--output", str(tmp_path / "generated.dfn"), "--views", "1"]
    )

    assert result.exit_code == 2
    assert "1 is not in the range x>=2" in result.output
