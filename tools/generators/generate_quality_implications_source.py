"""Generate deep or shared Quality Implications exercised by particle creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:quality_implications"


def generate_source_lines(  # noqa: PLR0913 - Each size scales independently.
    layers: int = 500,
    width: int = 2,
    fan_out: int = 2,
    assignments: int = 50,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    *,
    shared_quality: bool = False,
) -> list[str]:
    """Generate independently scalable implication depth, sharing, and assignments."""
    if layers < 1 or width < 1 or assignments < 1:
        raise ValueError("layers, width, and assignments must be at least 1")
    if not 1 <= fan_out <= width:
        raise ValueError("fan_out must be between 1 and width")
    lines: list[str] = []
    if shared_quality:
        lines.extend(_quality_action_lines(f"{fqun_prefix}:/shared", []))
    for layer in reversed(range(layers)):
        for index in range(width):
            implied = ["shared"] if shared_quality else []
            if layer < layers - 1:
                for offset in range(fan_out):
                    implied.append(f"quality_{layer + 1}_{(index + offset) % width}")
            lines.extend(
                _quality_action_lines(
                    f"{fqun_prefix}:/quality_{layer}_{index}", implied
                )
            )
    lines.extend(_test_action_lines(width, assignments, fqun_prefix))
    return lines


def _quality_action_lines(name: str, implied: Collection[str]) -> list[str]:
    """Generate an action that implies and triggers each of ``implied``."""
    lines = [f"define the potential action<{name}> {{"]
    for implied_name in implied:
        lines.append(f"    it also assigns the action</{implied_name}>.")
    lines.extend(
        [
            "    define the position<run>.",
            "    it happens when {",
            "        the position<run> has a particle.",
            "    } and it does {",
            "        destroy the particle in position<run>.",
        ]
    )
    for implied_name in implied:
        lines.append(
            f"        create a particle in action</{implied_name}>::position<run>."
        )
    lines.extend(["    }", "}"])
    return lines


def _test_action_lines(width: int, assignments: int, fqun_prefix: str) -> list[str]:
    """Generate the entry point, which assigns and triggers every first-layer action once per assignment."""
    lines = [
        f"define the potential action<{fqun_prefix}:/test> {{",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
    ]
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
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--layers",
    type=generator_cli.POSITIVE_INTEGER,
    default=500,
    show_default=True,
    help=(
        "Layers of quality actions; each action implies and triggers actions in"
        " the next layer. Sets the depth of the Quality Implications."
    ),
)
@click.option(
    "--width",
    type=generator_cli.POSITIVE_INTEGER,
    default=2,
    show_default=True,
    help=(
        "Quality actions per layer. 1 gives a single chain of implications;"
        " the source has layers times width actions."
    ),
)
@click.option(
    "--fan-out",
    type=generator_cli.POSITIVE_INTEGER,
    default=2,
    show_default=True,
    help=(
        "Next-layer actions each action implies and triggers, at most width."
        " Above 1, layers share implied qualities and the number of"
        " implication paths grows exponentially with layers."
    ),
)
@click.option(
    "--assignments",
    type=generator_cli.POSITIVE_INTEGER,
    default=50,
    show_default=True,
    help=(
        "Local positions in the test action that each assign every first-layer"
        " quality, then create a particle, trigger every first-layer action on"
        " it, and destroy it. Each repeats the whole implication graph."
    ),
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
@click.option(
    "--shared-quality",
    is_flag=True,
    help=(
        "Make every quality action also imply and trigger one shared action,"
        " which every action then implies both directly and through every"
        " layer after it."
    ),
)
def main(  # noqa: PLR0913, PLR0917 - Click passes the declared command options.
    output: Path,
    layers: int,
    width: int,
    fan_out: int,
    assignments: int,
    fqun_prefix: str,
    *,
    shared_quality: bool,
):
    """Generate implication chains (width=1) or shared layered implications."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                layers,
                width,
                fan_out,
                assignments,
                fqun_prefix,
                shared_quality=shared_quality,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
