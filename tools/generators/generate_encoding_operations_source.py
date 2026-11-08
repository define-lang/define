"""Generate many Encoding Operations with long bodies that execute each other."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:encoding_operations"
DEFAULT_OPERATIONS = 800
DEFAULT_STATEMENTS = 40
DEFAULT_CHAIN_DEPTH = 20

_ENCODING = "encoding<standard:/number/natural/ascii>"
_ADD = "encoding_operation<standard:/number/natural/ascii/add>"
_INDENT = "    "


def _indent(depth: int) -> str:
    return _INDENT * depth


def _quality_block(depth: int) -> list[str]:
    return [
        f"{_indent(depth)}it may only contain particles where {{",
        f"{_indent(depth + 1)}it has the {_ENCODING}.",
        f"{_indent(depth)}}}",
    ]


def _view_definition(name: str, direction: str | None, depth: int) -> list[str]:
    lines = [f"{_indent(depth)}define the view<{name}> {{"]
    if direction is not None:
        lines.append(f"{_indent(depth + 1)}{direction}")
    lines.extend(_quality_block(depth + 1))
    lines.append(f"{_indent(depth)}}}")
    return lines


def _execution(name: str, arguments: list[tuple[str, str]]) -> list[str]:
    lines = [f"{_indent(2)}execute the {name} {{"]
    for view, target in arguments:
        lines.append(f"{_indent(3)}with view<{view}> looking at {target}.")
    lines.append(f"{_indent(2)}}}")
    return lines


def _emit_statement(
    statement: int,
    source: str,
    target: str,
    callee: int | None,
    *,
    view_settings: bool,
) -> list[str]:
    if callee is not None:
        return _execution(
            f"encoding_operation</encoding/operation_{callee}>",
            [("number", source), ("result", target)],
        )
    if view_settings and statement % 2:
        copy = f"view<copy_{statement}>"
        return [
            *_view_definition(f"copy_{statement}", None, 2),
            f"{_indent(2)}set the value of {copy} from {source}.",
            *_execution(_ADD, [("a", source), ("b", copy), ("result", target)]),
        ]
    literal = f'literal<standard:/number>"{statement + 1}"'
    return _execution(_ADD, [("a", source), ("b", literal), ("result", target)])


def _emit_operation(
    prefix: str,
    operation: int,
    statements: int,
    callee: int | None,
    *,
    view_settings: bool,
) -> list[str]:
    lines = [
        f"define the encoding_operation<{prefix}:/encoding/operation_{operation}> {{",
        *_view_definition("number", "it is read.", 1),
        *_view_definition("result", "it is written.", 1),
        "",
        f"{_indent(1)}it does {{",
    ]
    for step in range(1, statements):
        lines.extend(_view_definition(f"step_{step}", None, 2))
    source = "view<number>"
    for statement in range(statements):
        target = (
            "view<result>"
            if statement == statements - 1
            else f"view<step_{statement + 1}>"
        )
        lines.extend(
            _emit_statement(
                statement,
                source,
                target,
                callee if statement == 0 else None,
                view_settings=view_settings,
            )
        )
        source = target
    lines.extend([f"{_indent(1)}}}", "}"])
    return lines


def generate_source_lines(
    operations: int = DEFAULT_OPERATIONS,
    statements: int = DEFAULT_STATEMENTS,
    chain_depth: int = DEFAULT_CHAIN_DEPTH,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    *,
    view_settings: bool = True,
) -> list[str]:
    """Return source lines for chains of Encoding Operations."""
    if operations < 1:
        raise ValueError(f"operations must be at least 1, got {operations}")
    if statements < 1:
        raise ValueError(f"statements must be at least 1, got {statements}")
    if chain_depth < 1:
        raise ValueError(f"chain_depth must be at least 1, got {chain_depth}")
    lines = ["# Generated Define source. Stresses Encoding Operations.", ""]
    for operation in range(operations):
        callee = None if operation % chain_depth == 0 else operation - 1
        lines.extend(
            _emit_operation(
                fqun_prefix,
                operation,
                statements,
                callee,
                view_settings=view_settings,
            )
        )
    lines.extend(
        [
            f"define the potential action<{fqun_prefix}:/test> {{",
            f"{_indent(1)}it happens when {{",
            f"{_indent(2)}this particle is created.",
            f"{_indent(1)}}} and it does {{",
            f"{_indent(2)}define the position<run>.",
            f"{_indent(2)}create a particle in position<run>.",
            f"{_indent(1)}}}",
            "}",
        ]
    )
    return lines


@click.command()
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--operations",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_OPERATIONS,
    show_default=True,
    help="Encoding Operations, all in sibling paths.",
)
@click.option(
    "--statements",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_STATEMENTS,
    show_default=True,
    help=(
        "Encoding Operation Execution Statements in each operation, chained"
        " through local views."
    ),
)
@click.option(
    "--chain-depth",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_CHAIN_DEPTH,
    show_default=True,
    help=(
        "Operations in each chain. Every operation but the first in a chain"
        " executes the previous one in its first statement."
    ),
)
@click.option(
    "--view-settings/--no-view-settings",
    default=True,
    show_default=True,
    help=(
        "Give every other statement a View Setting Statement copy of its"
        " input instead of a literal argument."
    ),
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(  # noqa: PLR0913 - Click passes the declared command options.
    output: Path,
    operations: int,
    statements: int,
    chain_depth: int,
    fqun_prefix: str,
    *,
    view_settings: bool,
):
    """Generate chains of Encoding Operations with long statement blocks."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                operations=operations,
                statements=statements,
                chain_depth=chain_depth,
                fqun_prefix=fqun_prefix,
                view_settings=view_settings,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
