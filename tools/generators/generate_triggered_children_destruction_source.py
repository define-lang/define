"""Generate a particle whose transitive children are filled by a tree of triggered actions, then destroyed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:triggered_children_destruction"


def generate_source_lines(
    depth: int = 20,
    fan_out: int = 2,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Generate ``depth`` actions that each fill ``fan_out`` children and trigger the next action on each.

    The source grows linearly with ``depth``, but the destroyed particle has
    exponentially many transitive children.
    """
    if depth < 1 or fan_out < 1:
        raise ValueError("depth and fan_out must be at least 1")
    lines: list[str] = []
    # A single-file program must define each global name before referencing it.
    for level in reversed(range(1, depth + 1)):
        if level < depth:
            for child in range(fan_out):
                lines.extend(
                    [
                        f"define the potential position<{fqun_prefix}:/child_{level}_{child}> {{",
                        "    it may only contain particles where {",
                        f"        it has the action</fill_{level + 1}>.",
                        "    }",
                        "}",
                    ]
                )
        lines.append(f"define the potential action<{fqun_prefix}:/fill_{level}> {{")
        if level < depth:
            lines.extend(
                f"    it also assigns the position</child_{level}_{child}>."
                for child in range(fan_out)
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
        if level < depth:
            for child in range(fan_out):
                lines.extend(
                    [
                        f"        create a particle in position</child_{level}_{child}>.",
                        f"        create a particle in position</child_{level}_{child}>::action</fill_{level + 1}>::position<run>.",
                    ]
                )
        lines.extend(["    }", "}"])
    lines.extend(
        [
            f"define the potential action<{fqun_prefix}:/test> {{",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
            "        define the position<filled> {",
            "            it may only contain particles where {",
            "                it has the action</fill_1>.",
            "            }",
            "        }",
            "        create a particle in position<filled>.",
            "        create a particle in position<filled>::action</fill_1>::position<run>.",
            "        destroy the particle in position<filled>.",
            "    }",
            "}",
        ]
    )
    return lines


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--depth", type=generator_cli.POSITIVE_INTEGER, default=20, show_default=True
)
@click.option(
    "--fan-out", type=generator_cli.POSITIVE_INTEGER, default=2, show_default=True
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
def main(output: Path, depth: int, fan_out: int, fqun_prefix: str):
    """Generate a destroyed particle with exponentially many triggered children."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output, generate_source_lines(depth, fan_out, fqun_prefix)
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
