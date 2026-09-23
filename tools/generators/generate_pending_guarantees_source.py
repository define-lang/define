"""Generate destruction queries with unrelated pending Action Guarantees."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:pending_guarantees"


def _chain(first: str, position_depth: int) -> str:
    return first + "".join(
        f"::position</child_{index}>" for index in range(position_depth - 1)
    )


def generate_source_lines(
    pending_positions: int = 1000,
    destroyed_positions: int = 100,
    call_depth: int = 2,
    *,
    position_depth: int = 1,
    automatic_destruction: bool = False,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Generate repeated or batched destruction beside deferred implied-position changes."""
    if pending_positions < 1 or destroyed_positions < 1:
        raise ValueError("pending_positions and destroyed_positions must be at least 1")
    if call_depth < 2:
        raise ValueError("call_depth must be at least 2")
    if position_depth < 1:
        raise ValueError("position_depth must be at least 1")
    lines = [f"define the potential position<{fqun_prefix}:/marker>."]
    for stage in reversed(range(call_depth)):
        lines.append(f"define the potential action<{fqun_prefix}:/stage_{stage}> {{")
        if stage == call_depth - 1:
            lines.append("    it also assigns the position</marker>.")
        else:
            lines.append(f"    it also assigns the action</stage_{stage + 1}>.")
        lines.extend(
            [
                "    define the position<run>.",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
            ]
        )
        if stage == call_depth - 1:
            lines.append("        create a particle in position</marker>.")
        else:
            lines.append(
                f"        create a particle in action</stage_{stage + 1}>::position<run>."
            )
        lines.extend(["        destroy the particle in position<run>.", "    }", "}"])
    for index in reversed(range(position_depth - 1)):
        lines.extend(
            [
                f"define the potential position<{fqun_prefix}:/child_{index}> {{",
                "    it may only contain particles where {",
            ]
        )
        if index == position_depth - 2:
            lines.extend(
                [
                    "        it has the action</stage_0>.",
                    "        it has the position</marker>.",
                ]
            )
        else:
            lines.append(f"        it has the position</child_{index + 1}>.")
        lines.extend(["    }", "}"])
    pending_quality = (
        "action</stage_0>" if position_depth == 1 else "position</child_0>"
    )
    saved_quality = "position</marker>" if position_depth == 1 else "position</child_0>"
    lines.extend(
        [
            f"define the potential action<{fqun_prefix}:/middle> {{",
            "    define the position<run>.",
        ]
    )
    for index in range(destroyed_positions):
        lines.append(f"    define the position<victim_{index}>.")
    for index in range(pending_positions):
        lines.extend(
            [
                f"    define the position<unrelated_{index}> {{",
                "        it may only contain particles where {",
                f"            it has the {pending_quality}.",
                "        }",
                "    }",
            ]
        )
    lines.extend(
        [
            "    it happens when {",
            "        the position<run> has a particle.",
            "    } and it does {",
            "        destroy the particle in position<run>.",
        ]
    )
    for index in range(pending_positions):
        chain = _chain(f"position<unrelated_{index}>", position_depth)
        lines.append(
            f"        create a particle in {chain}::action</stage_0>::position<run>."
        )
    for index in range(destroyed_positions):
        if automatic_destruction:
            lines.extend(
                [
                    f"        define the position<temporary_{index}>.",
                    f"        move the particle in position<victim_{index}> to position<temporary_{index}>.",
                ]
            )
        else:
            lines.append(f"        destroy the particle in position<victim_{index}>.")
    lines.extend(
        [
            "    }",
            "}",
            f"define the potential action<{fqun_prefix}:/test> {{",
            "    it also assigns the action</middle>.",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
        ]
    )
    for index in range(destroyed_positions):
        lines.append(
            f"        create a particle in action</middle>::position<victim_{index}>."
        )
    for index in range(pending_positions):
        for depth in range(1, position_depth + 1):
            chain = _chain(f"action</middle>::position<unrelated_{index}>", depth)
            lines.append(f"        create a particle in {chain}.")
    lines.append("        create a particle in action</middle>::position<run>.")
    for index in range(pending_positions):
        # The caller must consume every surviving interface particle; the marker
        # also verifies that the deferred changes are visible after the Move.
        saved_chain = _chain(f"position<saved_{index}>", position_depth)
        lines.extend(
            [
                f"        define the position<saved_{index}> {{",
                "            it may only contain particles where {",
                f"                it has the {saved_quality}.",
                "            }",
                "        }",
                f"        move the particle in action</middle>::position<unrelated_{index}> to position<saved_{index}>.",
                f"        destroy the particle in {saved_chain}::position</marker>.",
                f"        destroy the particle in position<saved_{index}>.",
            ]
        )
    lines.extend(["    }", "}"])
    return lines


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--pending-positions",
    type=generator_cli.POSITIVE_INTEGER,
    default=1000,
    show_default=True,
)
@click.option(
    "--destroyed-positions",
    type=generator_cli.POSITIVE_INTEGER,
    default=100,
    show_default=True,
)
@click.option("--call-depth", type=click.IntRange(min=2), default=2, show_default=True)
@click.option(
    "--position-depth",
    type=generator_cli.POSITIVE_INTEGER,
    default=1,
    show_default=True,
    help="Number of position names preceding each pending action.",
)
@click.option(
    "--automatic-destruction/--explicit-destruction", default=False, show_default=True
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
def main(
    output: Path,
    pending_positions: int,
    destroyed_positions: int,
    call_depth: int,
    position_depth: int,
    *,
    automatic_destruction: bool,
    fqun_prefix: str,
):
    """Generate pending guarantees that coexist with unrelated destruction queries."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(
                pending_positions,
                destroyed_positions,
                call_depth,
                position_depth=position_depth,
                automatic_destruction=automatic_destruction,
                fqun_prefix=fqun_prefix,
            ),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
