"""Generate independent occupancy errors with scalable source and name lengths."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:diagnostics"


def generate_source_lines(
    errors: int = 1000,
    name_length: int = 16,
    padding_lines: int = 0,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    *,
    indent_width: int = 4,
) -> list[str]:
    """Generate one duplicate Create per position after optional source padding."""
    if errors < 1 or name_length < 1:
        raise ValueError("errors and name_length must be at least 1")
    if padding_lines < 0:
        raise ValueError("padding_lines must be at least 0")
    if indent_width < 1:
        raise ValueError("indent_width must be at least 1")
    indent = " " * indent_width
    body_indent = indent * 2
    lines = ["# Padding before diagnostics."] * padding_lines
    lines.extend(
        [
            f"define the potential action<{fqun_prefix}:/test> {{",
            f"{indent}it happens when {{",
            f"{body_indent}this particle is created.",
            f"{indent}}} and it does {{",
        ]
    )
    for index in range(errors):
        name = f"value_{index}".ljust(name_length, "x")
        lines.extend(
            [
                f"{body_indent}define the position<{name}>.",
                f"{body_indent}create a particle in position<{name}>.",
                f"{body_indent}create a particle in position<{name}>.",
            ]
        )
    lines.extend([f"{indent}}}", "}"])
    return lines


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--errors", type=generator_cli.POSITIVE_INTEGER, default=1000, show_default=True
)
@click.option(
    "--name-length",
    type=generator_cli.POSITIVE_INTEGER,
    default=16,
    show_default=True,
    help="Minimum local-name length; longer names are needed for larger indexes.",
)
@click.option(
    "--padding-lines",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=0,
    show_default=True,
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
@click.option(
    "--indent-width",
    type=generator_cli.POSITIVE_INTEGER,
    default=4,
    show_default=True,
    help="Spaces per indentation level; values other than four also cause filesystem indentation diagnostics.",
)
def main(
    output: Path,
    errors: int,
    name_length: int,
    padding_lines: int,
    fqun_prefix: str,
    indent_width: int,
):
    """Generate invalid source for diagnostic collection and formatting workloads."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                errors,
                name_length,
                padding_lines,
                fqun_prefix,
                indent_width=indent_width,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
