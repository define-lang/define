"""Generate a Define source file with a large, dense action call graph.

Emits a single ``.dfn`` that compiles to zero diagnostics through the
non-filesystem validator, but whose shape stresses the reference-graph
traversal and the requirement / guarantee / destruction-contract
machinery rather than a single huge Action Statements Block.

The program is a layered directed acyclic graph of potential actions:

  * The root is the entry-point constructor action ``/test``. Its ``out``
    interface position is constrained to every layer-0 action, and its
    ``this particle is created`` body creates a particle in each layer-0
    action's ``src`` and ``trigger`` interface positions, triggering it.
  * Each non-leaf action references ``fan_out`` actions in the next layer
    through the Position Constraint Block of its ``out`` interface
    position (``it has the action</...>``). Those constraint references
    are the reference-graph edges the post-order traversal walks. The
    target set is a circulant (``(i + k) mod width``), so every target in
    the next layer has an in-degree of exactly ``fan_out`` -- dense
    fan-in -- while every source has an out-degree of exactly
    ``fan_out``.
  * Every action destroys the particle in its ``src`` interface position
    as the first reference to that position. Because the action did not
    create that particle and ``src`` is a contracted position, this both
    infers an Action Requirement (``src`` must be occupied) and records a
    Destruction Contract. A configurable fraction of actions additionally
    constrain ``src`` to carry a destructor, so destroying it drives the
    destruction cascade and destructor verification.
  * Each non-leaf action's body creates a particle in ``out`` (atomic
    creation assigns all of its constrained target actions) and then, for
    each target, creates a particle in the target's ``src`` and
    ``trigger`` -- satisfying the target's requirement and triggering it.

Definitions are emitted leaf-layer first so that every reference is a
back-reference to an already-defined name; in non-filesystem mode a
forward reference to a same-source name raises before any diagnostic.

Run via:
    bazelisk run //tools:generate_action_graph_source -- --output /tmp/graph.dfn
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:action_graph"
DEFAULT_LAYERS = 6
DEFAULT_WIDTH = 16
DEFAULT_FAN_OUT = 8
DEFAULT_DESTRUCTOR_FRACTION = 0.5

_MIN_LAYERS = 2
_MIN_WIDTH = 1
_OUTER_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "

_MARKER_POSITION = "/marker"
_MARKER_DESTRUCTOR = "/marker_destructor"


def _action_path(layer: int, index: int) -> str:
    return f"/layer{layer}_a{index}"


def _qualified(prefix: str, path: str) -> str:
    return f"{prefix}:{path}"


def _targets(index: int, width: int, fan_out: int) -> list[int]:
    """Return the next-layer target indices for the action at ``index``."""
    return [(index + offset) % width for offset in range(fan_out)]


def _has_destructor(global_index: int, stride: int) -> bool:
    return stride > 0 and global_index % stride == 0


def _destructor_stride(destructor_fraction: float) -> int:
    if destructor_fraction <= 0:
        return 0
    return max(1, round(1 / destructor_fraction))


def _emit_header() -> list[str]:
    return [
        "# Generated Define source. A dense layered action call graph.",
        "",
    ]


def _emit_destructor_definitions(prefix: str) -> list[str]:
    marker = _qualified(prefix, _MARKER_POSITION)
    destructor = _qualified(prefix, _MARKER_DESTRUCTOR)
    return [
        f"define the potential position<{marker}>.",
        "",
        f"define the potential action<{destructor}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{_MARKER_POSITION}>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is being destroyed.",
        f"{_OUTER_INDENT}}} and it does {{",
        # A destructor must leave every contracted position as it found it.
        # Create-then-destroy of the implied marker nets to zero.
        f"{_INNER_INDENT}create a particle in position<{_MARKER_POSITION}>.",
        f"{_INNER_INDENT}destroy the particle in position<{_MARKER_POSITION}>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_src_definition(*, carries_destructor: bool) -> list[str]:
    if not carries_destructor:
        return [f"{_OUTER_INDENT}define the position<src>."]
    return [
        f"{_OUTER_INDENT}define the position<src> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the action<{_MARKER_DESTRUCTOR}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
    ]


def _emit_out_definition(target_paths: list[str]) -> list[str]:
    lines = [
        f"{_OUTER_INDENT}define the position<out> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
    ]
    for target_path in target_paths:
        lines.append(f"{_DEEP_INDENT}it has the action<{target_path}>.")
    lines.extend(
        [
            f"{_INNER_INDENT}}}",
            f"{_OUTER_INDENT}}}",
        ]
    )
    return lines


def _emit_action_body(target_paths: list[str]) -> list[str]:
    # The first reference to ``src`` is a destroy of a particle the action
    # did not create, which infers the occupancy requirement and records
    # the Destruction Contract.
    lines = [f"{_INNER_INDENT}destroy the particle in position<src>."]
    if not target_paths:
        return lines
    lines.append(f"{_INNER_INDENT}create a particle in position<out>.")
    for target_path in target_paths:
        chain = f"position<out>::action<{target_path}>"
        lines.append(f"{_INNER_INDENT}create a particle in {chain}::position<src>.")
        lines.append(f"{_INNER_INDENT}create a particle in {chain}::position<trigger>.")
    return lines


def _emit_action(
    prefix: str,
    layer: int,
    index: int,
    target_paths: list[str],
    *,
    carries_destructor: bool,
) -> list[str]:
    name = _qualified(prefix, _action_path(layer, index))
    lines = [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}define the position<trigger>.",
        *_emit_src_definition(carries_destructor=carries_destructor),
    ]
    if target_paths:
        lines.extend(_emit_out_definition(target_paths))
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<trigger> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
            *_emit_action_body(target_paths),
            f"{_OUTER_INDENT}}}",
            "}",
            "",
        ]
    )
    return lines


def _emit_root(prefix: str, width: int) -> list[str]:
    name = _qualified(prefix, "/test")
    target_paths = [_action_path(0, index) for index in range(width)]
    lines = [
        f"define the potential action<{name}> {{",
        *_emit_out_definition(target_paths),
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is created.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<out>.",
    ]
    for target_path in target_paths:
        chain = f"position<out>::action<{target_path}>"
        lines.append(f"{_INNER_INDENT}create a particle in {chain}::position<src>.")
        lines.append(f"{_INNER_INDENT}create a particle in {chain}::position<trigger>.")
    lines.extend(
        [
            f"{_OUTER_INDENT}}}",
            "}",
            "",
        ]
    )
    return lines


def generate_source_lines(
    layers: int = DEFAULT_LAYERS,
    width: int = DEFAULT_WIDTH,
    fan_out: int = DEFAULT_FAN_OUT,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    destructor_fraction: float = DEFAULT_DESTRUCTOR_FRACTION,
) -> list[str]:
    """Return the generated source as a list of lines (no trailing newlines).

    ``layers`` x ``width`` actions are emitted in ``layers`` fully-connected
    bands; each non-leaf action references ``fan_out`` actions in the next
    band. ``destructor_fraction`` of actions constrain ``src`` to carry a
    destructor.
    """
    if layers < _MIN_LAYERS:
        raise ValueError(f"layers must be at least {_MIN_LAYERS}, got {layers}")
    if width < _MIN_WIDTH:
        raise ValueError(f"width must be at least {_MIN_WIDTH}, got {width}")
    if not 1 <= fan_out <= width:
        raise ValueError(f"fan_out must be in [1, {width}], got {fan_out}")
    if not 0 <= destructor_fraction <= 1:
        raise ValueError(
            f"destructor_fraction must be in [0, 1], got {destructor_fraction}"
        )

    stride = _destructor_stride(destructor_fraction)

    lines: list[str] = []
    lines.extend(_emit_header())
    if stride > 0:
        lines.extend(_emit_destructor_definitions(fqun_prefix))

    # Emit leaf-layer actions first so every reference is a back-reference
    # to an already-defined name.
    global_index = 0
    for layer in reversed(range(layers)):
        is_leaf = layer == layers - 1
        for index in range(width):
            if is_leaf:
                target_paths: list[str] = []
            else:
                target_paths = [
                    _action_path(layer + 1, target)
                    for target in _targets(index, width, fan_out)
                ]
            lines.extend(
                _emit_action(
                    fqun_prefix,
                    layer,
                    index,
                    target_paths,
                    carries_destructor=_has_destructor(global_index, stride),
                )
            )
            global_index += 1

    lines.extend(_emit_root(fqun_prefix, width))
    return lines


def _iter_with_newlines(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        yield line
        yield "\n"


def write_to_path(
    output: Path,
    layers: int = DEFAULT_LAYERS,
    width: int = DEFAULT_WIDTH,
    fan_out: int = DEFAULT_FAN_OUT,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    destructor_fraction: float = DEFAULT_DESTRUCTOR_FRACTION,
) -> int:
    """Write generated source to ``output``. Returns the number of lines written."""
    lines = generate_source_lines(
        layers=layers,
        width=width,
        fan_out=fan_out,
        fqun_prefix=fqun_prefix,
        destructor_fraction=destructor_fraction,
    )
    with output.open("w", encoding="utf-8") as f:
        for chunk in _iter_with_newlines(lines):
            _ = f.write(chunk)
    return len(lines)


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate a Define source file with a dense action call graph."
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the generated .dfn file",
    )
    _ = parser.add_argument(
        "--layers",
        type=int,
        default=DEFAULT_LAYERS,
        help=f"Number of action layers (default: {DEFAULT_LAYERS})",
    )
    _ = parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"Number of actions per layer (default: {DEFAULT_WIDTH})",
    )
    _ = parser.add_argument(
        "--fan-out",
        type=int,
        default=DEFAULT_FAN_OUT,
        help=(
            "Next-layer actions each action references; also the fan-in of"
            f" every target (default: {DEFAULT_FAN_OUT})"
        ),
    )
    _ = parser.add_argument(
        "--fqun-prefix",
        default=DEFAULT_FQUN_PREFIX,
        help=f"Universe prefix for every definition (default: {DEFAULT_FQUN_PREFIX})",
    )
    _ = parser.add_argument(
        "--destructor-fraction",
        type=float,
        default=DEFAULT_DESTRUCTOR_FRACTION,
        help=(
            "Fraction of actions whose destroyed src carries a destructor"
            f" (default: {DEFAULT_DESTRUCTOR_FRACTION})"
        ),
    )
    args = parser.parse_args()
    output_path = cast("Path", args.output)
    layers = cast("int", args.layers)
    width = cast("int", args.width)
    fan_out = cast("int", args.fan_out)
    fqun_prefix = cast("str", args.fqun_prefix)
    destructor_fraction = cast("float", args.destructor_fraction)
    written = write_to_path(
        output_path,
        layers=layers,
        width=width,
        fan_out=fan_out,
        fqun_prefix=fqun_prefix,
        destructor_fraction=destructor_fraction,
    )
    print(f"Wrote {written:,} lines to {output_path}")


if __name__ == "__main__":
    main()
