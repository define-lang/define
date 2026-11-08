"""Generate a long chain of value writes and reads through literal arguments."""

from __future__ import annotations

import itertools
import string
from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:value_setting"
DEFAULT_POSITIONS = 4
DEFAULT_QUALITIES_PER_POSITION = 64
DEFAULT_STATEMENTS = 30000
DEFAULT_LITERAL_DIGITS = 20

_MIN_POSITIONS = 2
# Python refuses to convert longer decimal strings to an int, which the
# decimal-to-binary Literal Parser does.
MAX_BINARY_LITERAL_DIGITS = 4300
_INDENT = "    "


def _literal(statement: int, digits: int) -> str:
    leading = str(statement % 9 + 1)
    rest = "".join(itertools.islice(itertools.cycle(string.digits), digits - 1))
    return f'literal<standard:/number>"{leading}{rest}"'


def _emit_positions(
    prefix: str, positions: int, qualities_per_position: int, value_quality: str
) -> list[str]:
    lines: list[str] = []
    for quality in range(qualities_per_position):
        lines.append(f"define the potential position<{prefix}:/extra_{quality}>.")
    for position in range(positions):
        lines.extend(
            [
                f"define the potential position<{prefix}:/value_{position}> {{",
                f"{_INDENT}it may only contain particles where {{",
                f"{_INDENT * 2}it has the {value_quality}.",
            ]
        )
        for quality in range(qualities_per_position):
            lines.append(f"{_INDENT * 2}it has the position</extra_{quality}>.")
        lines.extend([f"{_INDENT}}}", "}"])
    return lines


def _emit_statement(
    statement: int, positions: int, literal_digits: int, operation: str
) -> list[str]:
    source = f"position</value_{statement % positions}>"
    target = f"position</value_{(statement + 1) % positions}>"
    indent = _INDENT * 2
    if statement % 2:
        return [f"{indent}set the value of {target} from {source}."]
    return [
        f"{indent}execute the operation<{operation}> {{",
        f"{indent}{_INDENT}with view<a> looking at {source}.",
        f"{indent}{_INDENT}with view<b> looking at {_literal(statement, literal_digits)}.",
        f"{indent}{_INDENT}with view<result> looking at {target}.",
        f"{indent}}}",
    ]


def generate_source_lines(  # noqa: PLR0913 - Each size scales independently.
    positions: int = DEFAULT_POSITIONS,
    qualities_per_position: int = DEFAULT_QUALITIES_PER_POSITION,
    statements: int = DEFAULT_STATEMENTS,
    literal_digits: int = DEFAULT_LITERAL_DIGITS,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    *,
    binary_values: bool = False,
) -> list[str]:
    """Return source lines for a chain of value writes, each read by the next."""
    if positions < _MIN_POSITIONS:
        raise ValueError(
            f"positions must be at least {_MIN_POSITIONS}, got {positions}"
        )
    if qualities_per_position < 0:
        raise ValueError(
            f"qualities_per_position must not be negative, got {qualities_per_position}"
        )
    if statements < 1:
        raise ValueError(f"statements must be at least 1, got {statements}")
    if literal_digits < 1:
        raise ValueError(f"literal_digits must be at least 1, got {literal_digits}")
    if binary_values and literal_digits > MAX_BINARY_LITERAL_DIGITS:
        raise ValueError(
            f"literal_digits must be at most {MAX_BINARY_LITERAL_DIGITS} with binary values, got {literal_digits}"
        )
    if binary_values:
        value_quality = "value<standard:/binary>"
        operation = "standard:/binary/or"
    else:
        value_quality = "value<standard:/number/natural>"
        operation = "standard:/number/natural/add"
    lines = [
        "# Generated Define source. Stresses Value Setting and literals.",
        "",
        *_emit_positions(fqun_prefix, positions, qualities_per_position, value_quality),
        f"define the potential action<{fqun_prefix}:/test> {{",
    ]
    for position in range(positions):
        lines.append(f"{_INDENT}it also assigns the position</value_{position}>.")
    lines.extend(
        [
            f"{_INDENT}it happens when {{",
            f"{_INDENT * 2}this particle is created.",
            f"{_INDENT}}} and it does {{",
        ]
    )
    for position in range(positions):
        lines.append(f"{_INDENT * 2}create a particle in position</value_{position}>.")
    lines.append(
        f"{_INDENT * 2}set the value of position</value_0> from {_literal(0, literal_digits)}."
    )
    for statement in range(statements):
        lines.extend(_emit_statement(statement, positions, literal_digits, operation))
    lines.extend([f"{_INDENT}}}", "}"])
    return lines


@click.command()
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--positions",
    type=click.IntRange(min=_MIN_POSITIONS),
    default=DEFAULT_POSITIONS,
    show_default=True,
    help=(
        "Positions the chain cycles through. Fewer positions give each"
        " particle more uses."
    ),
)
@click.option(
    "--qualities-per-position",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_QUALITIES_PER_POSITION,
    show_default=True,
    help="Child positions each position's particles have besides their value quality.",
)
@click.option(
    "--statements",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_STATEMENTS,
    show_default=True,
    help=(
        "Statements in the chain, alternating Operation Execution Statements"
        " with a literal argument and Value Setting Statements. Each reads the"
        " position the previous one wrote."
    ),
)
@click.option(
    "--literal-digits",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_LITERAL_DIGITS,
    show_default=True,
    help=(
        "Decimal digits in every literal."
        f" At most {MAX_BINARY_LITERAL_DIGITS} with --binary-values."
    ),
)
@click.option(
    "--binary-values/--natural-values",
    default=False,
    show_default=True,
    help=(
        "Give the positions binary values, so every decimal literal is"
        " converted to binary."
    ),
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(  # noqa: PLR0913, PLR0917 - Click passes the declared command options.
    output: Path,
    positions: int,
    qualities_per_position: int,
    statements: int,
    literal_digits: int,
    fqun_prefix: str,
    *,
    binary_values: bool,
):
    """Generate a chain of value writes through literals and Value Setting Statements."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                positions=positions,
                qualities_per_position=qualities_per_position,
                statements=statements,
                literal_digits=literal_digits,
                fqun_prefix=fqun_prefix,
                binary_values=binary_values,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
