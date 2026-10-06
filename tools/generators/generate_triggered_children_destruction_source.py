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
    # As REARRANGE, but every particle it moves also has a Destructor.
    REARRANGE_DESTRUCTORS = "rearrange-destructors"
    # As LOCAL, but every action also triggers a shared action that has an
    # error on each child it fills, so the program reports that error.
    ERROR = "error"
    # As LOCAL, but every action also triggers, on each child it fills, an
    # action that creates a particle with a Destructor and then one that
    # destroys it.
    DEPENDENT_SIBLINGS = "dependent-siblings"
    # As LOCAL, but a Destructor creates and fills the local particle, which is
    # destroyed when the Destructor ends.
    IN_DESTRUCTOR = "in-destructor"
    # A Destructor triggers the first action on a particle in one of its
    # implied positions, so the program reports each particle that action
    # leaves there.
    IN_DESTRUCTOR_CONTRACTED = "in-destructor-contracted"
    # Every action triggers the next one on its own parent particle, once per
    # ``fan_out``, and destroys the particle that action created there before
    # triggering it again, so no child particles exist and the entry action
    # destroys only the one particle.
    SAME_PARTICLE = "same-particle"


def _rearranges(shape: Shape) -> bool:
    return shape in (Shape.REARRANGE, Shape.REARRANGE_DESTRUCTORS)


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
        case (
            Shape.LOCAL
            | Shape.DESTRUCTORS
            | Shape.REARRANGE
            | Shape.REARRANGE_DESTRUCTORS
            | Shape.ERROR
            | Shape.DEPENDENT_SIBLINGS
        ):
            if _rearranges(shape):
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
        case Shape.IN_DESTRUCTOR:
            return [
                f"define the potential action<{fqun_prefix}:/filling_destructor> {{",
                "    it happens when {",
                "        this particle is being destroyed.",
                "    } and it does {",
                *_position_with_fill("filled", "        "),
                "        create a particle in position<filled>.",
                "        create a particle in position<filled>::action</fill_1>::position<run>.",
                "    }",
                "}",
                *header,
                "        define the position<holder> {",
                "            it may only contain particles where {",
                "                it has the action</filling_destructor>.",
                "            }",
                "        }",
                "        create a particle in position<holder>.",
                "        destroy the particle in position<holder>.",
                "    }",
                "}",
            ]
        case Shape.IN_DESTRUCTOR_CONTRACTED:
            return [
                f"define the potential position<{fqun_prefix}:/kept> {{",
                "    it may only contain particles where {",
                "        it has the action</fill_1>.",
                "    }",
                "}",
                f"define the potential action<{fqun_prefix}:/filling_destructor> {{",
                "    it also assigns the position</kept>.",
                "    it happens when {",
                "        this particle is being destroyed.",
                "    } and it does {",
                "        create a particle in position</kept>::action</fill_1>::position<run>.",
                "    }",
                "}",
                *header,
                "        define the position<holder> {",
                "            it may only contain particles where {",
                "                it has the action</filling_destructor>.",
                "                it has the position</kept>.",
                "            }",
                "        }",
                "        create a particle in position<holder>.",
                "        create a particle in position<holder>::position</kept>.",
                "        destroy the particle in position<holder>.",
                "    }",
                "}",
            ]
        case Shape.SAME_PARTICLE:
            return [
                *header,
                *_position_with_fill("filled", "        "),
                "        create a particle in position<filled>.",
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


def _same_particle_lines(depth: int, fan_out: int, fqun_prefix: str) -> list[str]:
    lines: list[str] = []
    # A single-file program must define each global name before referencing it.
    for level in reversed(range(1, depth + 1)):
        lines.extend(
            [
                f"define the potential position<{fqun_prefix}:/made_{level}>.",
                f"define the potential action<{fqun_prefix}:/fill_{level}> {{",
                f"    it also assigns the position</made_{level}>.",
            ]
        )
        if level < depth:
            lines.extend(
                [
                    f"    it also assigns the action</fill_{level + 1}>.",
                    f"    it also assigns the position</made_{level + 1}>.",
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
        if level < depth:
            for _ in range(fan_out):
                lines.extend(
                    [
                        f"        create a particle in action</fill_{level + 1}>::position<run>.",
                        f"        destroy the particle in position</made_{level + 1}>.",
                    ]
                )
        lines.extend(
            [f"        create a particle in position</made_{level}>.", "    }", "}"]
        )
    lines.extend(_entry_lines(Shape.SAME_PARTICLE, fqun_prefix))
    return lines


def _shape_definitions(shape: Shape, fqun_prefix: str) -> list[str]:
    lines: list[str] = []
    if shape in (
        Shape.DESTRUCTORS,
        Shape.DEPENDENT_SIBLINGS,
        Shape.REARRANGE_DESTRUCTORS,
    ):
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
    if _rearranges(shape):
        for name in ("item", "kept", "done"):
            if shape == Shape.REARRANGE_DESTRUCTORS:
                lines.extend(
                    [
                        f"define the potential position<{fqun_prefix}:/{name}> {{",
                        "    it may only contain particles where {",
                        "        it has the action</cleanup>.",
                        "    }",
                        "}",
                    ]
                )
            else:
                lines.append(f"define the potential position<{fqun_prefix}:/{name}>.")
        lines.append(f"define the potential position<{fqun_prefix}:/mark>.")
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
    if shape == Shape.DEPENDENT_SIBLINGS:
        lines.extend(
            [
                f"define the potential position<{fqun_prefix}:/item> {{",
                "    it may only contain particles where {",
                "        it has the action</cleanup>.",
                "    }",
                "}",
                f"define the potential action<{fqun_prefix}:/make_item> {{",
                "    it also assigns the position</item>.",
                "    define the position<run>.",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        destroy the particle in position<run>.",
                "        create a particle in position</item>.",
                "    }",
                "}",
                f"define the potential action<{fqun_prefix}:/clear_item> {{",
                "    it also assigns the position</item>.",
                "    define the position<run>.",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        destroy the particle in position<run>.",
                "        destroy the particle in position</item>.",
                "    }",
                "}",
            ]
        )
    if shape == Shape.ERROR:
        lines.extend(
            [
                f"define the potential position<{fqun_prefix}:/detail>.",
                f"define the potential action<{fqun_prefix}:/broken> {{",
                "    define the position<run>.",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        destroy the particle in position<run>.",
                "        define the position<scratch> {",
                "            it may only contain particles where {",
                "                it has the position</detail>.",
                "            }",
                "        }",
                "        create a particle in position<scratch>::position</detail>.",
                "    }",
                "}",
            ]
        )
    return lines


def _child_position_definitions(
    level: int, fan_out: int, shape: Shape, fqun_prefix: str
) -> list[str]:
    lines: list[str] = []
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
        if shape == Shape.ERROR:
            lines.append("        it has the action</broken>.")
        if shape == Shape.DEPENDENT_SIBLINGS:
            lines.extend(
                [
                    "        it has the action</make_item>.",
                    "        it has the action</clear_item>.",
                ]
            )
        if _rearranges(shape):
            lines.extend(
                f"        it has the {quality}."
                for quality in (
                    "position</item>",
                    "position</kept>",
                    "position</done>",
                )
            )
        lines.extend(["    }", "}"])
    return lines


def _fill_action_lines(
    level: int, depth: int, fan_out: int, shape: Shape, fqun_prefix: str
) -> list[str]:
    lines: list[str] = []
    lines.append(f"define the potential action<{fqun_prefix}:/fill_{level}> {{")
    if level < depth:
        lines.extend(
            f"    it also assigns the position</child_{level}_{child}>."
            for child in range(fan_out)
        )
    if _rearranges(shape):
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
    if _rearranges(shape):
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
            if _rearranges(shape):
                lines.append(
                    f"        create a particle in {child_name}::position</item>."
                )
            lines.append(
                f"        create a particle in {child_name}::action</fill_{level + 1}>::position<run>."
            )
            if shape == Shape.ERROR:
                lines.append(
                    f"        create a particle in {child_name}::action</broken>::position<run>."
                )
            if shape == Shape.DEPENDENT_SIBLINGS:
                lines.extend(
                    [
                        f"        create a particle in {child_name}::action</make_item>::position<run>.",
                        f"        create a particle in {child_name}::action</clear_item>::position<run>.",
                    ]
                )
            if _rearranges(shape):
                lines.append(
                    f"        move the particle in {child_name}::position</kept> to {child_name}::position</done>."
                )
    lines.extend(["    }", "}"])
    return lines


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
    if shape == Shape.SAME_PARTICLE:
        return _same_particle_lines(depth, fan_out, fqun_prefix)
    lines = _shape_definitions(shape, fqun_prefix)
    # A single-file program must define each global name before referencing it.
    for level in reversed(range(1, depth + 1)):
        if level < depth:
            lines.extend(
                _child_position_definitions(level, fan_out, shape, fqun_prefix)
            )
        lines.extend(_fill_action_lines(level, depth, fan_out, shape, fqun_prefix))
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
