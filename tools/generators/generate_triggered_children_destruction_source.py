"""Generate a particle whose transitive children are filled by a tree of triggered actions, then destroyed."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:triggered_children_destruction"


class Shape(enum.StrEnum):
    """Where the particle with triggered children is destroyed."""

    # The entry action destroys a local particle.
    LOCAL = "local"
    # As LOCAL, but every triggered child also has a Destructor.
    DESTRUCTORS = "destructors"
    # An action destroys a particle from an interface position, which makes a
    # Destruction Contract.
    CONTRACTED = "contracted"
    # An action moves the particle between interface positions before the entry
    # action destroys it.
    MOVE = "move"
    # As LOCAL, but every action also moves a particle its caller created below
    # the particle it acts on, triggers another action on that particle, and
    # moves a particle that its callees moved.
    REARRANGE = "rearrange"


def _position_with_fill(
    name: str, indent: str, additional_qualities: tuple[str, ...] = ()
) -> list[str]:
    return [
        f"{indent}define the position<{name}> {{",
        f"{indent}    it may only contain particles where {{",
        f"{indent}        it has the action</fill_1>.",
        *(f"{indent}        it has the {quality}." for quality in additional_qualities),
        f"{indent}    }}",
        f"{indent}}}",
    ]


def _entry_lines(shape: Shape, fqun_prefix: str) -> list[str]:
    header = [
        f"define the potential action<{fqun_prefix}:/test> {{",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
    ]
    match shape:
        case Shape.LOCAL | Shape.DESTRUCTORS | Shape.REARRANGE:
            if shape == Shape.REARRANGE:
                qualities = ("position</item>",)
                item = [
                    "        create a particle in position<filled>::position</item>."
                ]
            else:
                qualities = ()
                item = []
            return [
                *header,
                *_position_with_fill("filled", "        ", qualities),
                "        create a particle in position<filled>.",
                *item,
                "        create a particle in position<filled>::action</fill_1>::position<run>.",
                "        destroy the particle in position<filled>.",
                "    }",
                "}",
            ]
        case Shape.CONTRACTED:
            return [
                f"define the potential action<{fqun_prefix}:/destroyer> {{",
                "    define the position<run>.",
                *_position_with_fill("filled", "    "),
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        create a particle in position<filled>::action</fill_1>::position<run>.",
                "        destroy the particle in position<filled>.",
                "        destroy the particle in position<run>.",
                "    }",
                "}",
                f"define the potential action<{fqun_prefix}:/test> {{",
                "    it also assigns the action</destroyer>.",
                "    it happens when {",
                "        this particle is created.",
                "    } and it does {",
                "        create a particle in action</destroyer>::position<filled>.",
                "        create a particle in action</destroyer>::position<run>.",
                "    }",
                "}",
            ]
        case Shape.MOVE:
            return [
                f"define the potential action<{fqun_prefix}:/mover> {{",
                "    define the position<run>.",
                *_position_with_fill("source", "    "),
                *_position_with_fill("destination", "    "),
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        create a particle in position<source>::action</fill_1>::position<run>.",
                "        move the particle in position<source> to position<destination>.",
                "        destroy the particle in position<run>.",
                "    }",
                "}",
                f"define the potential action<{fqun_prefix}:/test> {{",
                "    it also assigns the action</mover>.",
                "    it happens when {",
                "        this particle is created.",
                "    } and it does {",
                "        create a particle in action</mover>::position<source>.",
                "        create a particle in action</mover>::position<run>.",
                "        destroy the particle in action</mover>::position<destination>.",
                "    }",
                "}",
            ]


def generate_source_lines(
    depth: int = 20,
    fan_out: int = 2,
    shape: Shape = Shape.LOCAL,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Generate ``depth`` actions that each fill ``fan_out`` children and trigger the next action on each.

    The source grows linearly with ``depth``, but the destroyed particle has
    exponentially many transitive children.
    """
    if depth < 1 or fan_out < 1:
        raise ValueError("depth and fan_out must be at least 1")
    lines: list[str] = []
    if shape == Shape.DESTRUCTORS:
        lines.extend(
            [
                f"define the potential action<{fqun_prefix}:/cleanup> {{",
                "    it happens when {",
                "        this particle is being destroyed.",
                "    } and it does {",
                "        define the position<scratch>.",
                "        create a particle in position<scratch>.",
                "    }",
                "}",
            ]
        )
    if shape == Shape.REARRANGE:
        lines.extend(
            f"define the potential position<{fqun_prefix}:/{name}>."
            for name in ("item", "kept", "done", "mark")
        )
        lines.extend(
            [
                f"define the potential action<{fqun_prefix}:/stamp> {{",
                "    it also assigns the position</mark>.",
                "    define the position<run>.",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        destroy the particle in position<run>.",
                "        create a particle in position</mark>.",
                "    }",
                "}",
            ]
        )
    # A single-file program must define each global name before referencing it.
    for level in reversed(range(1, depth + 1)):
        if level < depth:
            for child in range(fan_out):
                lines.extend(
                    [
                        f"define the potential position<{fqun_prefix}:/child_{level}_{child}> {{",
                        "    it may only contain particles where {",
                        f"        it has the action</fill_{level + 1}>.",
                    ]
                )
                if shape == Shape.DESTRUCTORS:
                    lines.append("        it has the action</cleanup>.")
                if shape == Shape.REARRANGE:
                    lines.extend(
                        f"        it has the {quality}."
                        for quality in (
                            "position</item>",
                            "position</kept>",
                            "position</done>",
                        )
                    )
                lines.extend(["    }", "}"])
        lines.append(f"define the potential action<{fqun_prefix}:/fill_{level}> {{")
        if level < depth:
            lines.extend(
                f"    it also assigns the position</child_{level}_{child}>."
                for child in range(fan_out)
            )
        if shape == Shape.REARRANGE:
            lines.extend(
                [
                    "    it also assigns the position</item>.",
                    "    it also assigns the position</kept>.",
                    "    it also assigns the action</stamp>.",
                ]
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
        if shape == Shape.REARRANGE:
            lines.extend(
                [
                    "        move the particle in position</item> to position</kept>.",
                    "        create a particle in action</stamp>::position<run>.",
                ]
            )
        if level < depth:
            for child in range(fan_out):
                child_name = f"position</child_{level}_{child}>"
                lines.append(f"        create a particle in {child_name}.")
                if shape == Shape.REARRANGE:
                    lines.append(
                        f"        create a particle in {child_name}::position</item>."
                    )
                lines.append(
                    f"        create a particle in {child_name}::action</fill_{level + 1}>::position<run>."
                )
                if shape == Shape.REARRANGE:
                    lines.append(
                        f"        move the particle in {child_name}::position</kept> to {child_name}::position</done>."
                    )
        lines.extend(["    }", "}"])
    lines.extend(_entry_lines(shape, fqun_prefix))
    return lines


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--depth", type=generator_cli.POSITIVE_INTEGER, default=20, show_default=True
)
@click.option(
    "--fan-out", type=generator_cli.POSITIVE_INTEGER, default=2, show_default=True
)
@click.option(
    "--shape",
    type=click.Choice([shape.value for shape in Shape]),
    default=Shape.LOCAL.value,
    show_default=True,
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
def main(output: Path, depth: int, fan_out: int, shape: str, fqun_prefix: str):
    """Generate a destroyed particle with exponentially many triggered children."""
    written = generator_cli.invoke(
        lambda: generator_io.write_lines(
            output,
            generate_source_lines(depth, fan_out, Shape(shape), fqun_prefix),
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
