"""Generate a many-file Define project with heavy cross-file referencing.

Each generated file defines one potential position whose Position Constraint
Block references positions defined in deeper layers. Every such reference is a
global reference into another file, so the project exercises cross-file
reference resolution and the reference graph rather than the contents of any
one file.
"""

import argparse
import random
import shutil
from pathlib import Path
from typing import cast

DEFAULT_UNIVERSE_NAME = "mv:define-lang.org:bench"
DEFAULT_MODULES = 24000
DEFAULT_LAYERS = 20
DEFAULT_FAN_OUT = 3
DEFAULT_UTILITY_FRACTION = 0.3
DEFAULT_SEED = 7
_PACKAGE_COUNT = 512


def _definition_path(index: int) -> str:
    return f"/lib/pkg{index % _PACKAGE_COUNT}/m{index}"


def _file_path(index: int) -> str:
    return f"lib/pkg{index % _PACKAGE_COUNT}/m{index}.dfn"


def _definition(universe_name: str, index: int, targets: list[int]) -> str:
    name = f"define the potential position<{universe_name}:{_definition_path(index)}>"
    if not targets:
        return f"{name}.\n"
    constraints = "".join(
        f"        it has the position<{_definition_path(target)}>.\n"
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


def generate_project_files(
    modules: int = DEFAULT_MODULES,
    layers: int = DEFAULT_LAYERS,
    fan_out: int = DEFAULT_FAN_OUT,
    utility_fraction: float = DEFAULT_UTILITY_FRACTION,
    seed: int = DEFAULT_SEED,
    universe_name: str = DEFAULT_UNIVERSE_NAME,
) -> dict[str, str]:
    """Return every file of the project, keyed by its path below the project root."""
    if layers < 2:
        raise ValueError(f"layers must be at least 2, got {layers}")
    if modules < layers:
        raise ValueError(f"modules must be at least layers, got {modules}")
    if fan_out < 1:
        raise ValueError(f"fan_out must be at least 1, got {fan_out}")
    if not 0 <= utility_fraction <= 1:
        raise ValueError(f"utility_fraction must be in [0, 1], got {utility_fraction}")

    # A seeded generator makes the project shape reproducible; nothing here
    # needs cryptographic randomness.
    generator = random.Random(seed)  # noqa: S311
    width = max(1, modules // layers)
    files = {
        ".define/project/config.defcl": (
            f'project: {{ universe_name: "{universe_name}" }}\n'
        )
    }
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
        files[_file_path(index)] = _definition(universe_name, index, targets)

    # The entry file reaches the first layer, from which the walk reaches the
    # rest; definitions no layer references are never validated.
    entry_constraints = "".join(
        f"        it has the position<{_definition_path(target)}>.\n"
        for target in range(min(width, modules))
    )
    files["test.dfn"] = (
        f"define the potential position<{universe_name}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"{entry_constraints}"
        "    }\n"
        "}\n"
    )
    return files


def main():
    """Write a generated project to the requested directory."""
    parser = argparse.ArgumentParser(
        description="""Generate a many-file Define project with heavy cross-file referencing.

Writes a project directory rather than one file: each file defines one
potential position whose Position Constraint Block references positions
defined in deeper layers, so every reference is a global reference into
another file. The other profiling sources are each a single file, so this is
the only shape that exercises per-file parallel validation, cross-file
reference resolution, and the reference graph. --utility-fraction of
references aim at a small set of deepest-layer definitions, giving the graph
the high fan-in that real dependency graphs have.

Scale it with --modules for file count and --layers for reference depth.
--seed makes the shape reproducible. The generated project validates to zero
diagnostics; its entry point is a position rather than a constructor action,
so profile it through validate_program rather than a full compile.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = parser.add_argument(
        "--output", type=Path, required=True, help="Project root to write"
    )
    _ = parser.add_argument(
        "--modules",
        type=int,
        default=DEFAULT_MODULES,
        help=f"Definitions, one per file (default: {DEFAULT_MODULES})",
    )
    _ = parser.add_argument(
        "--layers",
        type=int,
        default=DEFAULT_LAYERS,
        help=f"Layers of references from entry to leaf (default: {DEFAULT_LAYERS})",
    )
    _ = parser.add_argument(
        "--fan-out",
        type=int,
        default=DEFAULT_FAN_OUT,
        help=f"References each definition makes (default: {DEFAULT_FAN_OUT})",
    )
    _ = parser.add_argument(
        "--utility-fraction",
        type=float,
        default=DEFAULT_UTILITY_FRACTION,
        help=(
            "Share of references aimed at a small set of deepest-layer"
            f" definitions (default: {DEFAULT_UTILITY_FRACTION})"
        ),
    )
    _ = parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Makes the generated shape reproducible (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args()

    output = cast("Path", args.output)
    files = generate_project_files(
        modules=cast("int", args.modules),
        layers=cast("int", args.layers),
        fan_out=cast("int", args.fan_out),
        utility_fraction=cast("float", args.utility_fraction),
        seed=cast("int", args.seed),
    )
    if output.exists():
        shutil.rmtree(output)
    for relative_path, content in files.items():
        file_path = output / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        _ = file_path.write_text(content, encoding="utf-8")
    print(f"Wrote {len(files)} files to {output}")


if __name__ == "__main__":
    main()
