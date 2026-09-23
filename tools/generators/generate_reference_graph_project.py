"""Generate a many-file Define project with heavy cross-file referencing.

Each generated file defines one potential position whose Position Constraint
Block references positions defined in deeper layers. Every such reference is a
global reference into another file, so the project exercises cross-file
reference resolution and the reference graph rather than the contents of any
one file.
"""

from __future__ import annotations

import enum
import random
from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

DEFAULT_UNIVERSE_NAME = "mv:define-lang.org:bench"
DEFAULT_MODULES = 80000
DEFAULT_LAYERS = 20
DEFAULT_FAN_OUT = 3
DEFAULT_UTILITY_FRACTION = 0.3
DEFAULT_SEED = 7
_PACKAGE_COUNT = 512


class Shape(enum.StrEnum):
    """Reference patterns with independently scalable definition counts."""

    LAYERED = "layered"
    INDEPENDENT = "independent"
    CHAIN = "chain"
    FAN_IN = "fan-in"
    DEPTH_UPDATES = "depth-updates"
    DIAMONDS = "diamonds"
    BOTTLENECKS = "bottlenecks"
    CYCLES = "cycles"
    MISSING = "missing"
    CONFIG_CHAIN = "config-chain"


def _definition_path(index: int, path_depth: int = 0) -> str:
    return "/" + "directory/" * path_depth + f"lib/pkg{index % _PACKAGE_COUNT}/m{index}"


def _file_path(index: int, path_depth: int = 0) -> str:
    return _definition_path(index, path_depth)[1:] + ".dfn"


def _definition(
    universe_name: str, index: int, targets: Sequence[int], path_depth: int = 0
) -> str:
    name = f"define the potential position<{universe_name}:{_definition_path(index, path_depth)}>"
    if not targets:
        return f"{name}.\n"
    constraints = "".join(
        f"        it has the position<{_definition_path(target, path_depth)}>.\n"
        for target in targets
    )
    return (
        f"{name} {{\n"
        "    it may only contain particles where {\n"
        f"{constraints}"
        "    }\n"
        "}\n"
    )


def _targets_for(
    generator: random.Random,
    index: int,
    layer: int,
    layers: int,
    width: int,
    fan_out: int,
    utility_fraction: float,
) -> list[int]:
    if layer >= layers - 1:
        return []
    utility_count = max(1, int(width * utility_fraction))
    targets: list[int] = []
    for _ in range(fan_out):
        if generator.random() < utility_fraction:
            # A definition every layer reaches, giving the graph high fan-in.
            targets.append((layers - 1) * width + generator.randrange(utility_count))
        else:
            target_layer = min(layers - 1, layer + 1 + int(generator.expovariate(2.0)))
            targets.append(target_layer * width + generator.randrange(width))
    return [target for target in dict.fromkeys(targets) if target != index]


def _structured_targets(
    shape: Shape, modules: int, fan_out: int
) -> Iterator[Sequence[int]]:
    match shape:
        case Shape.INDEPENDENT:
            for _ in range(modules):
                yield ()
        case Shape.CHAIN:
            for index in range(modules - 1):
                yield (index + 1,)
            yield ()
        case Shape.FAN_IN:
            for _ in range(modules - 1):
                yield (modules - 1,)
            yield ()
        case Shape.DEPTH_UPDATES:
            yield range(1, modules)
            if modules > 1:
                yield ()
            for index in range(2, modules):
                yield (index - 1,)
        case Shape.CYCLES:
            yield range(1, modules)
            for _ in range(modules - 1):
                yield (0,)
        case Shape.MISSING:
            for _ in range(modules):
                yield (modules,)
        case Shape.DIAMONDS | Shape.BOTTLENECKS:
            start = 0
            width = 1
            while start + width < modules:
                next_start = start + width
                next_width = (
                    min(2 if shape == Shape.DIAMONDS else fan_out, modules - next_start)
                    if width == 1
                    else 1
                )
                targets = range(next_start, next_start + next_width)
                for _ in range(width):
                    yield targets
                start = next_start
                width = next_width
            for _ in range(width):
                yield ()
        case _:
            raise ValueError(f"Not a structured shape: {shape}")


def _config_chain(modules: int, universe_name: str, path_depth: int) -> dict[str, str]:
    files: dict[str, str] = {}
    for index in range(modules + 1):
        directory = "dependency/" * index
        universe = (
            universe_name if index == 0 else f"{universe_name}_dependency_{index}"
        )
        files[directory + ".define/project/config.defcl"] = (
            f'project: {{ universe_name: "{universe}" }}\n'
        )
        next_universe = f"{universe_name}_dependency_{index + 1}"
        target = f"{next_universe}:{_definition_path(index + 1, path_depth)}"
        if index < modules:
            files[directory + ".define/deps/local.defcl"] = (
                f'deps: {{ local: [{{ universe_name: "{next_universe}" path: "dependency" }}] }}\n'
            )
        if index == 0:
            files["test.dfn"] = (
                f"define the potential action<{universe_name}:/test> {{\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<reference> {\n"
                "            it may only contain particles where {\n"
                f"                it has the position<{target}>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<reference>.\n"
                f"        create a particle in position<reference>::position<{target}>.\n"
                "    }\n"
                "}\n"
            )
        else:
            header = f"define the potential position<{universe}:{_definition_path(index, path_depth)}>"
            if index == modules:
                definition = header + ".\n"
            else:
                definition = (
                    f"{header} {{\n"
                    "    it may only contain particles where {\n"
                    f"        it has the position<{target}>.\n"
                    "    }\n"
                    "}\n"
                )
            files[directory + _file_path(index, path_depth)] = definition
    return files


def generate_project_files(
    modules: int = DEFAULT_MODULES,
    layers: int = DEFAULT_LAYERS,
    fan_out: int = DEFAULT_FAN_OUT,
    utility_fraction: float = DEFAULT_UTILITY_FRACTION,
    seed: int = DEFAULT_SEED,
    universe_name: str = DEFAULT_UNIVERSE_NAME,
    shape: Shape = Shape.LAYERED,
    path_depth: int = 0,
    *,
    reverse_references: bool = False,
) -> dict[str, str]:
    """Return every file of the project, keyed by its path below the project root."""
    if modules < 1:
        raise ValueError("modules must be at least 1")
    if path_depth < 0:
        raise ValueError("path_depth must be at least 0")
    if shape == Shape.LAYERED and layers < 2:
        raise ValueError(f"layers must be at least 2, got {layers}")
    if shape == Shape.LAYERED and modules < layers:
        raise ValueError(f"modules must be at least layers, got {modules}")
    if fan_out < 1:
        raise ValueError(f"fan_out must be at least 1, got {fan_out}")
    if not 0 <= utility_fraction <= 1:
        raise ValueError(f"utility_fraction must be in [0, 1], got {utility_fraction}")
    if shape == Shape.CONFIG_CHAIN:
        return _config_chain(modules, universe_name, path_depth)

    files = {
        ".define/project/config.defcl": (
            f'project: {{ universe_name: "{universe_name}" }}\n'
        )
    }
    if shape == Shape.LAYERED:
        # A seeded generator makes the project shape reproducible; nothing here
        # needs cryptographic randomness.
        generator = random.Random(seed)  # noqa: S311
        width = modules // layers
        for index in range(modules):
            targets = _targets_for(
                generator,
                index,
                index // width,
                layers,
                width,
                fan_out,
                utility_fraction,
            )
            files[_file_path(index, path_depth)] = _definition(
                universe_name,
                index,
                targets[::-1] if reverse_references else targets,
                path_depth,
            )
        entry_targets = range(width)
    else:
        if shape in (Shape.INDEPENDENT, Shape.MISSING):
            entry_targets = range(modules)
        elif shape == Shape.FAN_IN:
            entry_targets = range(max(1, modules - 1))
        else:
            entry_targets = range(1)
        for index, targets in enumerate(_structured_targets(shape, modules, fan_out)):
            files[_file_path(index, path_depth)] = _definition(
                universe_name,
                index,
                targets[::-1] if reverse_references else targets,
                path_depth,
            )

    if reverse_references:
        entry_targets = entry_targets[::-1]

    # The entry file references the first layer so validation follows references
    # through every layer; definitions no layer references are never validated.
    entry_constraints = "".join(
        (
            f"                it has the position<{_definition_path(target, path_depth)}>.\n"
        )
        for target in entry_targets
    )
    entry_references = "".join(
        (
            "        create a particle in "
            f"position<references>::position<{_definition_path(target, path_depth)}>.\n"
        )
        for target in entry_targets
    )
    files["test.dfn"] = (
        f"define the potential action<{universe_name}:/test> {{\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<references> {\n"
        "            it may only contain particles where {\n"
        f"{entry_constraints}"
        "            }\n"
        "        }\n"
        "        create a particle in position<references>.\n"
        f"{entry_references}"
        "    }\n"
        "}\n"
    )
    return files


def write_project(output: Path, files: dict[str, str]):
    """Write a project to a new directory."""
    output.mkdir(parents=True)
    for relative_path, content in files.items():
        file_path = output / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        _ = file_path.write_text(content, encoding="utf-8")


@click.command()
@click.option(
    "--reverse-references",
    is_flag=True,
    help="Reverse reference order in each definition, preserving the dependency graph.",
)
@click.option(
    "--shape",
    type=click.Choice([shape.value for shape in Shape]),
    default=Shape.LAYERED.value,
    show_default=True,
)
@click.option(
    "--path-depth",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=0,
    show_default=True,
    help="Additional directory components in every generated definition path.",
)
@click.option(
    "--output",
    type=generator_cli.OUTPUT_DIRECTORY,
    required=True,
    help="New project directory.",
)
@click.option(
    "--modules",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_MODULES,
    show_default=True,
    help="Definitions to emit, one per file.",
)
@click.option(
    "--layers",
    type=click.IntRange(min=2),
    default=DEFAULT_LAYERS,
    show_default=True,
    help="Layers of references from entry to leaf.",
)
@click.option(
    "--fan-out",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_FAN_OUT,
    show_default=True,
    help="References each definition makes.",
)
@click.option(
    "--utility-fraction",
    type=generator_cli.FRACTION,
    default=DEFAULT_UTILITY_FRACTION,
    show_default=True,
    help="Share of references aimed at deepest-layer utility definitions.",
)
@click.option(
    "--seed",
    type=int,
    default=DEFAULT_SEED,
    show_default=True,
    help="Seed that makes the generated shape reproducible.",
)
@click.option(
    "--universe-name",
    default=DEFAULT_UNIVERSE_NAME,
    show_default=True,
    help="Universe name for generated definitions.",
)
def main(
    output: Path,
    modules: int,
    layers: int,
    fan_out: int,
    utility_fraction: float,
    seed: int,
    universe_name: str,
    shape: str,
    path_depth: int,
    *,
    reverse_references: bool,
):
    """Generate a many-file Define project with heavy cross-file referencing.

    Writes a project directory rather than one file: each file defines one
    potential position whose Position Constraint Block references positions
    defined in deeper layers, so every reference is a global reference into
    another file. The other profiling sources are each a single file, so this is
    the only shape that exercises per-file parallel validation, cross-file
    reference resolution, and the reference graph. --utility-fraction of
    references aim at a small set of deepest-layer definitions, giving the graph
    the high fan-in that real dependency graphs have.

    Scale it with --modules for file count and --layers for reference depth.
    --seed makes the shape reproducible. Compile the generated project with
    test.dfn as its entry file. It compiles to zero diagnostics through its
    constructor action entry point. At the defaults this writes 80,002 files
    and requires hundreds of MiB, so choose a fresh destination with sufficient
    space. The destination must not already exist; remove it after retaining any
    profiles that need it.
    """
    files = generator_cli.invoke(
        lambda: generate_project_files(
            modules=modules,
            layers=layers,
            fan_out=fan_out,
            utility_fraction=utility_fraction,
            seed=seed,
            universe_name=universe_name,
            shape=Shape(shape),
            reverse_references=reverse_references,
            path_depth=path_depth,
        )
    )
    generator_cli.invoke(lambda: write_project(output, files))
    generator_cli.report_written("files", len(files), output)


if __name__ == "__main__":
    main()
