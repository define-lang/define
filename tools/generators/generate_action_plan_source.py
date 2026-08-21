"""Generate Define source that stresses per-action code-generation planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path


DEFAULT_FQUN_PREFIX = "mv:define-lang.org:action_plan"
DEFAULT_ACTIONS = 1000
DEFAULT_CHAINS_PER_ACTION = 16
DEFAULT_TOPOLOGY_GROUPS = 100
DEFAULT_TOPOLOGY_WIDTH = 64

_OUTER_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "


def _emit_leaf_positions(fqun_prefix: str, topology_width: int) -> list[str]:
    lines: list[str] = []
    for child in range(topology_width):
        lines.append(f"define the potential position<{fqun_prefix}:/child_{child}>.")
    lines.append("")
    return lines


def _emit_substantial_action(
    fqun_prefix: str, action_index: int, chains_per_action: int
) -> list[str]:
    lines = [f"define the potential action<{fqun_prefix}:/action_{action_index}> {{"]
    lines.append(f"{_OUTER_INDENT}define the position<run>.")
    for chain in range(chains_per_action):
        lines.append(f"{_OUTER_INDENT}define the position<value_{chain}>.")
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
        ]
    )
    for chain in range(chains_per_action):
        lines.append(f"{_INNER_INDENT}create a particle in position<value_{chain}>.")
        lines.append(f"{_INNER_INDENT}destroy the particle in position<value_{chain}>.")
    lines.extend([f"{_OUTER_INDENT}}}", "}", ""])
    return lines


def _emit_topology_action(
    fqun_prefix: str, topology_groups: int, topology_width: int
) -> list[str]:
    lines = [f"define the potential action<{fqun_prefix}:/topology> {{"]
    lines.append(f"{_OUTER_INDENT}define the position<run>.")
    for group in range(topology_groups):
        lines.extend(
            [
                f"{_OUTER_INDENT}define the position<parent_{group}> {{",
                f"{_INNER_INDENT}it may only contain particles where {{",
            ]
        )
        for child in range(topology_width):
            lines.append(f"{_DEEP_INDENT}it has the position</child_{child}>.")
        lines.extend([f"{_INNER_INDENT}}}", f"{_OUTER_INDENT}}}"])
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
        ]
    )
    for group in range(topology_groups):
        parent = f"position<parent_{group}>"
        lines.append(f"{_INNER_INDENT}create a particle in {parent}.")
        for child in range(topology_width):
            lines.append(
                f"{_INNER_INDENT}create a particle in {parent}::position</child_{child}>."
            )
        lines.append(f"{_INNER_INDENT}destroy the particle in {parent}.")
    lines.extend([f"{_OUTER_INDENT}}}", "}", ""])
    return lines


def _emit_entry_constructor(fqun_prefix: str) -> list[str]:
    return [
        f"define the potential action<{fqun_prefix}:/boot> {{",
        f"{_OUTER_INDENT}define the position<_noop>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is created.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<_noop>.",
        f"{_INNER_INDENT}destroy the particle in position<_noop>.",
        f"{_OUTER_INDENT}}}",
        "}",
    ]


def generate_source_lines(
    actions: int = DEFAULT_ACTIONS,
    chains_per_action: int = DEFAULT_CHAINS_PER_ACTION,
    topology_groups: int = DEFAULT_TOPOLOGY_GROUPS,
    topology_width: int = DEFAULT_TOPOLOGY_WIDTH,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Return source lines for independently scalable Action Plan shapes."""
    lines = ["# Generated Define source. Stresses Action Plan construction.", ""]
    if topology_groups > 0:
        lines.extend(_emit_leaf_positions(fqun_prefix, topology_width))
    for action_index in range(actions):
        lines.extend(
            _emit_substantial_action(fqun_prefix, action_index, chains_per_action)
        )
    if topology_groups > 0:
        lines.extend(
            _emit_topology_action(fqun_prefix, topology_groups, topology_width)
        )
    lines.extend(_emit_entry_constructor(fqun_prefix))
    return lines


def write_to_path(
    output: Path,
    actions: int = DEFAULT_ACTIONS,
    chains_per_action: int = DEFAULT_CHAINS_PER_ACTION,
    topology_groups: int = DEFAULT_TOPOLOGY_GROUPS,
    topology_width: int = DEFAULT_TOPOLOGY_WIDTH,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> int:
    """Write the generated source and return its line count."""
    return generator_io.write_lines(
        output,
        generate_source_lines(
            actions=actions,
            chains_per_action=chains_per_action,
            topology_groups=topology_groups,
            topology_width=topology_width,
            fqun_prefix=fqun_prefix,
        ),
    )


@click.command()
@click.option("--output", type=generator_cli.OUTPUT_FILE, required=True)
@click.option(
    "--actions",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_ACTIONS,
    show_default=True,
)
@click.option(
    "--chains-per-action",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_CHAINS_PER_ACTION,
    show_default=True,
)
@click.option(
    "--topology-groups",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_TOPOLOGY_GROUPS,
    show_default=True,
)
@click.option(
    "--topology-width",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_TOPOLOGY_WIDTH,
    show_default=True,
)
@click.option("--fqun-prefix", default=DEFAULT_FQUN_PREFIX, show_default=True)
def main(
    output: Path,
    actions: int,
    chains_per_action: int,
    topology_groups: int,
    topology_width: int,
    fqun_prefix: str,
):
    """Generate many substantial actions and Action Fragment fan-out/joins."""
    written = generator_cli.invoke(
        lambda: write_to_path(
            output,
            actions=actions,
            chains_per_action=chains_per_action,
            topology_groups=topology_groups,
            topology_width=topology_width,
            fqun_prefix=fqun_prefix,
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
