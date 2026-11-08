"""Generate a Value Operation with many Interface Views, executed many times."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:wide_value_operations"
DEFAULT_VIEWS = 200
DEFAULT_EXECUTIONS = 200
DEFAULT_OPERATION_CALLERS = 4

_MIN_VIEWS = 2
_VALUE_QUALITY = "value<standard:/number/natural>"
# The compiler cannot yet generate code for every Encoding Operation that
# logical_operation<standard:/number/add> may select, so the fold multiplies.
_LOGICAL_OPERATION = "logical_operation<standard:/number/multiply>"
_WIDE_OPERATION = "/product"
_TOTAL_POSITION = "/total"
_INDENT = "    "


def _indent(depth: int) -> str:
    return _INDENT * depth


def _quality_block(depth: int) -> list[str]:
    return [
        f"{_indent(depth)}it may only contain particles where {{",
        f"{_indent(depth + 1)}it has the {_VALUE_QUALITY}.",
        f"{_indent(depth)}}}",
    ]


def _view_definition(name: str, direction: str | None, depth: int) -> list[str]:
    lines = [f"{_indent(depth)}define the view<{name}> {{"]
    if direction is not None:
        lines.append(f"{_indent(depth + 1)}{direction}")
    lines.extend(_quality_block(depth + 1))
    lines.append(f"{_indent(depth)}}}")
    return lines


def _interface_views(views: int) -> list[str]:
    lines: list[str] = []
    for view in range(views):
        lines.extend(_view_definition(f"a_{view}", "it is read.", 1))
    lines.extend(_view_definition("result", "it is written.", 1))
    lines.append("")
    return lines


def _execution(
    name: str, arguments: Iterable[tuple[str, str]], depth: int
) -> list[str]:
    lines = [f"{_indent(depth)}execute the {name} {{"]
    for view, target in arguments:
        lines.append(f"{_indent(depth + 1)}with view<{view}> looking at {target}.")
    lines.append(f"{_indent(depth)}}}")
    return lines


def _emit_wide_operation(prefix: str, views: int) -> list[str]:
    lines = [f"define the operation<{prefix}:{_WIDE_OPERATION}> {{"]
    lines.extend(_interface_views(views))
    lines.append(f"{_indent(1)}it does {{")
    for product in range(1, views - 1):
        lines.extend(_view_definition(f"product_{product}", None, 2))
    previous = "view<a_0>"
    for view in range(1, views):
        result = "view<result>" if view == views - 1 else f"view<product_{view}>"
        lines.extend(
            _execution(
                _LOGICAL_OPERATION,
                [("a", previous), ("b", f"view<a_{view}>"), ("result", result)],
                2,
            )
        )
        previous = result
    lines.extend([f"{_indent(1)}}}", "}"])
    return lines


def _emit_caller(prefix: str, caller: int, views: int) -> list[str]:
    lines = [f"define the operation<{prefix}:/caller_{caller}> {{"]
    lines.extend(_interface_views(views))
    lines.append(f"{_indent(1)}it does {{")
    arguments: list[tuple[str, str]] = []
    for view in range(views):
        arguments.append((f"a_{view}", f"view<a_{view}>"))
    arguments.append(("result", "view<result>"))
    lines.extend(_execution(f"operation<{_WIDE_OPERATION}>", arguments, 2))
    lines.extend([f"{_indent(1)}}}", "}"])
    return lines


def _local_position(name: str) -> list[str]:
    lines = [f"{_indent(2)}define the position<{name}> {{"]
    lines.extend(_quality_block(3))
    lines.append(f"{_indent(2)}}}")
    return lines


def _emit_entry_point(
    prefix: str, views: int, executions: int, operation_callers: int
) -> list[str]:
    lines = [
        f"define the potential position<{prefix}:{_TOTAL_POSITION}> {{",
        *_quality_block(1),
        "}",
        f"define the potential action<{prefix}:/test> {{",
        f"{_indent(1)}it also assigns the position<{_TOTAL_POSITION}>.",
        f"{_indent(1)}it happens when {{",
        f"{_indent(2)}this particle is created.",
        f"{_indent(1)}}} and it does {{",
    ]
    for view in range(views):
        lines.extend(_local_position(f"input_{view}"))
    for execution in range(executions - 1):
        lines.extend(_local_position(f"result_{execution}"))
    for view in range(views):
        lines.extend(
            (
                f"{_indent(2)}create a particle in position<input_{view}>.",
                f'{_indent(2)}set the value of position<input_{view}> from literal<standard:/number>"{view + 1}".',
            )
        )
    operations = [_WIDE_OPERATION]
    for caller in range(operation_callers):
        operations.append(f"/caller_{caller}")
    previous = "position<input_0>"
    for execution in range(executions):
        result = (
            f"position<{_TOTAL_POSITION}>"
            if execution == executions - 1
            else f"position<result_{execution}>"
        )
        arguments = [("a_0", previous)]
        for view in range(1, views):
            arguments.append((f"a_{view}", f"position<input_{view}>"))
        arguments.append(("result", result))
        lines.append(f"{_indent(2)}create a particle in {result}.")
        operation = operations[execution % len(operations)]
        lines.extend(_execution(f"operation<{operation}>", arguments, 2))
        previous = result
    lines.extend([f"{_indent(1)}}}", "}"])
    return lines


def generate_source_lines(
    views: int = DEFAULT_VIEWS,
    executions: int = DEFAULT_EXECUTIONS,
    operation_callers: int = DEFAULT_OPERATION_CALLERS,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Return source lines for a wide Value Operation and its executions."""
    if views < _MIN_VIEWS:
        raise ValueError(f"views must be at least {_MIN_VIEWS}, got {views}")
    if executions < 1:
        raise ValueError(f"executions must be at least 1, got {executions}")
    if operation_callers < 0:
        raise ValueError(
            f"operation_callers must not be negative, got {operation_callers}"
        )
    lines = [
        "# Generated Define source. Stresses wide Value Operations.",
        "",
        *_emit_wide_operation(fqun_prefix, views),
    ]
    for caller in range(operation_callers):
        lines.extend(_emit_caller(fqun_prefix, caller, views))
    lines.extend(_emit_entry_point(fqun_prefix, views, executions, operation_callers))
    return lines


@click.command()
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--views",
    type=click.IntRange(min=_MIN_VIEWS),
    default=DEFAULT_VIEWS,
    show_default=True,
    help=(
        "Input Interface Views of the wide Value Operation, folded together"
        " through a chain of local views. Every execution passes one argument"
        " per view."
    ),
)
@click.option(
    "--executions",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_EXECUTIONS,
    show_default=True,
    help=(
        "Operation Execution Statements in the entry action. Each reads the"
        " previous execution's result and writes a fresh position."
    ),
)
@click.option(
    "--operation-callers",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_OPERATION_CALLERS,
    show_default=True,
    help=(
        "Value Operations with the same Interface Views that execute the wide"
        " operation. The entry action's executions cycle through the wide"
        " operation and these callers."
    ),
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(
    output: Path,
    views: int,
    executions: int,
    operation_callers: int,
    fqun_prefix: str,
):
    """Generate a wide Value Operation executed by an action and other operations."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                views=views,
                executions=executions,
                operation_callers=operation_callers,
                fqun_prefix=fqun_prefix,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
