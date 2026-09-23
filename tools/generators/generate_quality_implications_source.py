"""Generate deep or shared Quality Implications exercised by particle creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:quality_implications"


def generate_source_lines(
    layers: int = 100,
    width: int = 2,
    fan_out: int = 2,
    assignments: int = 10,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Generate independently scalable implication depth, sharing, and assignments."""
    if layers < 1 or width < 1 or assignments < 1:
        raise ValueError("layers, width, and assignments must be at least 1")
    if not 1 <= fan_out <= width:
        raise ValueError("fan_out must be between 1 and width")
    lines: list[str] = []
    for layer in reversed(range(layers)):
        for index in range(width):
            name = f"{fqun_prefix}:/quality_{layer}_{index}"
            lines.append(f"define the potential action<{name}> {{")
            if layer < layers - 1:
                for offset in range(fan_out):
                    target = (index + offset) % width
                    lines.append(
                        f"    it also assigns the action</quality_{layer + 1}_{target}>."
                    )
            lines.extend(
                [
                    "    define the position<run>.",
                    "    it happens when {",
                    "        the position<run> has a particle.",
                    "    } and it does {",
                    "        destroy the particle in position<run>.",
                ]
            )
            if layer < layers - 1:
                for offset in range(fan_out):
                    target = (index + offset) % width
                    lines.append(
                        f"        create a particle in action</quality_{layer + 1}_{target}>::position<run>."
                    )
            lines.extend(["    }", "}"])
    lines.extend(
        [
            f"define the potential action<{fqun_prefix}:/test> {{",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
        ]
    )
    for assignment in range(assignments):
        lines.extend(
            [
                f"        define the position<sample_{assignment}> {{",
                "            it may only contain particles where {",
            ]
        )
        for index in range(width):
            lines.append(f"                it has the action</quality_0_{index}>.")
        lines.extend(
            [
                "            }",
                "        }",
                f"        create a particle in position<sample_{assignment}>.",
            ]
        )
        for index in range(width):
            lines.append(
                f"        create a particle in position<sample_{assignment}>::action</quality_0_{index}>::position<run>."
            )
        lines.append(f"        destroy the particle in position<sample_{assignment}>.")
    lines.extend(["    }", "}"])
    return lines


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--layers", type=generator_cli.POSITIVE_INTEGER, default=100, show_default=True
)
@click.option(
    "--width", type=generator_cli.POSITIVE_INTEGER, default=2, show_default=True
)
@click.option(
    "--fan-out", type=generator_cli.POSITIVE_INTEGER, default=2, show_default=True
)
@click.option(
    "--assignments", type=generator_cli.POSITIVE_INTEGER, default=10, show_default=True
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
def main(
    output: Path,
    layers: int,
    width: int,
    fan_out: int,
    assignments: int,
    fqun_prefix: str,
):
    """Generate implication chains (width=1) or shared layered implications."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(layers, width, fan_out, assignments, fqun_prefix),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
