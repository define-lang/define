"""Generate a large, syntactically-diverse Define source file for stress testing.

Emits a single ``.dfn`` whose contents produce zero diagnostics when run
through the non-filesystem validator. The body is a cycle of self-
contained particle-state-conserving blocks: every create is paired with
a destroy, and every move is followed by a destroy of the destination.
The cycle's chain blocks deliberately never touch their chain heads
(``position<interface_to_g0>``, ``position</g_0>``) outside of a chained
reference, so those heads stay in their indeterminate initial state and
remain valid chain entries for every iteration. The source exercises a
broad slice of the grammar:

  * A pool of top-level potential position and potential action definitions
    in the same FQUN as the main action. Each pool position declares
    ``it has the position</g_(i+1)>`` so long chains through the pool
    satisfy the chain-element constraint check. Pool actions have
    net-zero bodies (create-then-destroy in ``_noop``).
  * Standalone potential position definitions in 2-part and 3-part FQUN
    forms in other universes, to exercise the multi-format FQUN parser
    path. They are not referenced from the main action because the
    validator's non-filesystem mode currently raises KeyError when
    processing a reference edge to a cross-universe target.
  * Positions with constraint blocks, and a constructor action carrying
    quality implications whose ``this particle is created`` body pairs
    every create with a destroy so the constructor runs net-zero.
  * A bulk action whose body interleaves blocks rooted in three kinds of
    names -- the action's interface positions, fresh inner local
    positions defined inside the action statements block, and implied
    positions/actions on the action -- so no single root dominates. The
    bulk action also has a destructor action that triggers on
    ``this particle is being destroyed``.
  * Every ``ActionStatement`` kind -- inner local position definitions
    (simple and constrained), ``create``, ``move``, and ``destroy`` --
    using a mix of interface, inner-local, and implied references, plus
    chained references including very long chains (up to the configured
    maximum) rooted at implied positions. Long-chain blocks walk down
    the chain populating each intermediate before the final create, then
    walk back up destroying them, so the per-segment chain rule is
    satisfied even when the same head is exercised by chain blocks of
    different lengths in the same iteration.
  * Standalone comments, trailing comments, and blank lines.

Run via:
    bazelisk run //tools:generate_large_define_source -- --output /tmp/big.dfn
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

DEFAULT_FQUN = "mv:define-lang.org:large_program:/test"
DEFAULT_TARGET_LINES = 1_000_000
DEFAULT_MAX_CHAIN_LENGTH = 100

# Cross-universe position definitions in 2-part and 3-part FQUN forms,
# emitted to exercise the multi-format FQUN parser path. Currently
# unreferenced from the main action: in non-filesystem mode, a back-
# reference to a cross-universe target tries to resolve a sub-root for a
# project root that was never registered, raising KeyError from
# path_tracker.has_sub_root before any diagnostic can be produced.
_CROSS_UNIVERSE_2PART = "demo.example:demo_universe:/demo_2part"
_CROSS_UNIVERSE_3PART = "demo_mv:demo.example:demo_universe:/demo_3part"

_MIN_TARGET_LINES = 400
_MIN_CHAIN_LENGTH = 2
_OUTER_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "
_QUAD_INDENT = "                "

# Interface positions defined in the main action body. Each pairs with a
# distinct shape so blocks can be rooted at them without all chains
# falling through the implied ``g_0`` constraint.
_INTERFACE_SIMPLE = "interface_simple"
_INTERFACE_TO_G0 = "interface_to_g0"
_INTERFACE_TO_G2 = "interface_to_g2"
_INTERFACE_DST = "interface_dst"

# Implied-target indices on the main action and on the
# constructor-action-with-implications definition.
_IMPLIED_POSITION_INDEX = 0
_IMPLIED_INTERFACE_TO_G2_INDEX = 2
_IMPLIED_INNER_CONSTRAINT_INDEX = 4
_POSITION_IMPLICATIONS_IMPLIED_POSITION_INDEX = 0
_POSITION_IMPLICATIONS_IMPLIED_ACTION_INDEX = 1


def _global_path(i: int) -> str:
    return f"/g_{i}"


def _action_path(i: int) -> str:
    return f"/a_{i}"


def _split_fqun(fqun: str) -> tuple[str, str]:
    """Split ``fqun`` into ``(prefix, path)``; raises ``ValueError`` if malformed."""
    sep_index = fqun.rfind(":")
    if sep_index <= 0:
        raise ValueError(
            "fqun must be of the form '<prefix>:/path'"
            + f" (e.g., {DEFAULT_FQUN!r}), got {fqun!r}"
        )
    prefix = fqun[:sep_index]
    path = fqun[sep_index + 1 :]
    if not path.startswith("/"):
        raise ValueError(f"fqun path component must start with '/', got {path!r}")
    prefix_parts = prefix.split(":")
    if len(prefix_parts) not in {2, 3}:
        raise ValueError(
            "fqun prefix must have 2 or 3 colon-separated parts,"
            + f" got {len(prefix_parts)} in {prefix!r}"
        )
    return prefix, path


def _qualified_global_name(prefix: str, i: int, *, is_action: bool = False) -> str:
    """Return ``<prefix>:<path>`` for index ``i`` in the pool universe."""
    suffix = _action_path(i) if is_action else _global_path(i)
    return f"{prefix}:{suffix}"


def _short_global_name(i: int, *, is_action: bool = False) -> str:
    """Return path-only ``</path>`` form. Resolves to the enclosing FQUN."""
    return _action_path(i) if is_action else _global_path(i)


def _emit_header() -> list[str]:
    return [
        "# Generated Define source. Exercises a broad slice of the grammar.",
        "",
    ]


def _emit_simple_position_pool(prefix: str, num_globals: int) -> list[str]:
    # Emit positions in reverse order (g_(N-1) first, g_0 last) so each
    # ``it has the position</g_(i+1)>`` constraint is a back-reference to
    # an already-defined name. The non-filesystem validator does not load
    # files for same-source back-references; forward references would
    # instead trigger NoProjectRootInNonFilesystemContext.
    lines: list[str] = []
    for i in reversed(range(num_globals)):
        name = _qualified_global_name(prefix, i)
        if i == num_globals - 1:
            lines.append(f"define the potential position<{name}>.")
            continue
        next_name = _short_global_name(i + 1)
        lines.extend(
            [
                f"define the potential position<{name}> {{",
                f"{_OUTER_INDENT}it may only contain particles where {{",
                f"{_INNER_INDENT}it has the position<{next_name}>.",
                f"{_OUTER_INDENT}}}",
                "}",
                "",
            ]
        )
    return lines


def _emit_cross_universe_positions() -> list[str]:
    return [
        f"define the potential position<{_CROSS_UNIVERSE_2PART}>.",
        f"define the potential position<{_CROSS_UNIVERSE_3PART}>.",
        "",
    ]


def _emit_simple_action_pool(prefix: str, num_actions: int) -> list[str]:
    lines: list[str] = []
    for i in range(num_actions):
        name = _qualified_global_name(prefix, i, is_action=True)
        # Pool action bodies create and then destroy the particle so the
        # action runs net-zero. External callers that chain through these
        # actions (e.g. ``action</a_i>::position<_noop>``) can therefore
        # pair their own create with a destroy without colliding with a
        # state left behind by the pool action's own body.
        lines.extend(
            [
                f"define the potential action<{name}> {{",
                f"{_OUTER_INDENT}define the position<run>.",
                f"{_OUTER_INDENT}define the position<_noop>.",
                f"{_OUTER_INDENT}it happens when {{",
                f"{_INNER_INDENT}the position<run> has a particle.",
                f"{_OUTER_INDENT}}} and it does {{",
                f"{_INNER_INDENT}create a particle in position<_noop>.",
                f"{_INNER_INDENT}destroy the particle in position<_noop>.",
                f"{_OUTER_INDENT}}}",
                "}",
                "",
            ]
        )
    return lines


def _emit_constrained_position(prefix: str, index: int) -> list[str]:
    name = _qualified_global_name(prefix, index)
    return [
        f"define the potential position<{name}> {{",
        f"{_OUTER_INDENT}it may only contain particles where {{",
        f"{_INNER_INDENT}it has the position<{_short_global_name(0)}>.",
        f"{_INNER_INDENT}it has the action<{_short_global_name(1, is_action=True)}>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_action_with_implications_and_constructor(
    prefix: str, index: int
) -> list[str]:
    name = _qualified_global_name(prefix, index, is_action=True)
    implied_position = _short_global_name(_POSITION_IMPLICATIONS_IMPLIED_POSITION_INDEX)
    implied_action = _short_global_name(
        _POSITION_IMPLICATIONS_IMPLIED_ACTION_INDEX, is_action=True
    )
    return [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{implied_position}>.",
        f"{_OUTER_INDENT}it also assigns the action<{implied_action}>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is created.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<{implied_position}>.",
        f"{_INNER_INDENT}destroy the particle in position<{implied_position}>.",
        f"{_INNER_INDENT}# Trailing comment in constructor block",
        f"{_INNER_INDENT}create a particle in action<{implied_action}>::position<_noop>.",
        f"{_INNER_INDENT}destroy the particle in action<{implied_action}>::position<_noop>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_destructor_action(fqun_path: str) -> list[str]:
    return [
        f"define the potential action<{fqun_path}> {{",
        f"{_OUTER_INDENT}define the position<_noop>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is being destroyed.",
        f"{_OUTER_INDENT}}} and it does {{",
        # A destructor must leave every position in the state it was in.
        # Create-then-destroy nets to zero so no guarantee diagnostic fires.
        f"{_INNER_INDENT}create a particle in position<_noop>.",
        f"{_INNER_INDENT}destroy the particle in position<_noop>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _chain_reference(length: int, num_globals: int) -> str:
    elements = [
        f"position<{_short_global_name(i % num_globals)}>" for i in range(length)
    ]
    return "::".join(elements)


def _create_destroy(reference: str) -> list[str]:
    return [
        f"{_INNER_INDENT}create a particle in {reference}.",
        f"{_INNER_INDENT}destroy the particle in {reference}.",
    ]


def _block_interface_simple() -> list[str]:
    return _create_destroy(f"position<{_INTERFACE_SIMPLE}>")


def _block_inner_local_simple(step: int) -> list[str]:
    name = f"inner_{step}"
    return [
        f"{_INNER_INDENT}define the position<{name}>.",
        *_create_destroy(f"position<{name}>"),
    ]


def _block_inner_local_constrained(step: int) -> list[str]:
    name = f"inner_c_{step}"
    target = _short_global_name(_IMPLIED_INNER_CONSTRAINT_INDEX)
    # Inner local positions start empty and the chain rule (spec
    # "Position References") requires every intermediate position in a
    # chain to already contain a particle. Populate the inner before the
    # chain create, then drain it after the chain destroy.
    return [
        f"{_INNER_INDENT}define the position<{name}> {{",
        f"{_DEEP_INDENT}it may only contain particles where {{",
        f"{_QUAD_INDENT}it has the position<{target}>.",
        f"{_DEEP_INDENT}}}",
        f"{_INNER_INDENT}}}",
        f"{_INNER_INDENT}create a particle in position<{name}>.",
        f"{_INNER_INDENT}create a particle in position<{name}>::position<{target}>.",
        f"{_INNER_INDENT}destroy the particle in position<{name}>::position<{target}>.",
        f"{_INNER_INDENT}destroy the particle in position<{name}>.",
    ]


def _block_implied_action_chain(step: int, num_actions: int) -> list[str]:
    ai = step % num_actions
    return _create_destroy(
        f"action<{_short_global_name(ai, is_action=True)}>::position<_noop>"
    )


# Chain blocks below never touch the chain's head position directly --
# only as the first element of a chained name. The validator allows
# chain access to an interface or implied position while its state is
# indeterminate (the initial state at the top of the action body), but
# once that position has been explicitly created or destroyed its state
# becomes known and the chain rule fires. Keeping the head untouched
# leaves it indeterminate for every iteration of the cycle.
def _block_interface_to_implied_chain() -> list[str]:
    target = _short_global_name(_IMPLIED_INTERFACE_TO_G2_INDEX)
    return _create_destroy(f"position<{_INTERFACE_TO_G2}>::position<{target}>")


def _block_implied_chain(length: int, num_globals: int) -> list[str]:
    # Walk down the chain populating each intermediate, then walk back
    # up destroying them. The chain rule (spec "Position References")
    # requires every position in a chain except the last to already
    # contain a particle, so a single ``create a particle in
    # g_0::g_1::g_2::...`` would fail unless every shorter prefix is
    # already populated.
    lines: list[str] = []
    for prefix_length in range(2, length + 1):
        chain = _chain_reference(prefix_length, num_globals)
        lines.append(f"{_INNER_INDENT}create a particle in {chain}.")
    for prefix_length in range(length, 1, -1):
        chain = _chain_reference(prefix_length, num_globals)
        lines.append(f"{_INNER_INDENT}destroy the particle in {chain}.")
    return lines


def _block_move_interface() -> list[str]:
    source = f"position<{_INTERFACE_SIMPLE}>"
    destination = f"position<{_INTERFACE_DST}>"
    return [
        f"{_INNER_INDENT}create a particle in {source}.",
        f"{_INNER_INDENT}move the particle in {source} to {destination}.",
        f"{_INNER_INDENT}destroy the particle in {destination}.",
    ]


def _block_move_interface_chain() -> list[str]:
    target = _short_global_name(_IMPLIED_POSITION_INDEX)
    source = f"position<{_INTERFACE_TO_G0}>::position<{target}>"
    destination = f"position<{_INTERFACE_DST}>"
    return [
        f"{_INNER_INDENT}create a particle in {source}.",
        f"{_INNER_INDENT}move the particle in {source} to {destination}.",
        f"{_INNER_INDENT}destroy the particle in {destination}.",
    ]


def _block_comment(step: int) -> list[str]:
    return [f"{_INNER_INDENT}# cycle marker {step}"]


_BODY_BLOCK_COUNT = 11


def _next_body_block(
    step: int, num_globals: int, num_actions: int, max_chain_length: int
) -> list[str]:
    """Return one self-contained, state-conserving block of body lines."""
    # ``_INTERFACE_TO_G0`` and ``position</g_0>`` are the chain heads
    # used by later kinds in this cycle; the cycle therefore does not
    # include a "direct create+destroy" block for either of them, since
    # touching them once would transition them out of the indeterminate
    # state the chain blocks rely on.
    kind = step % _BODY_BLOCK_COUNT
    if kind == 0:
        return _block_interface_simple()
    if kind == 1:
        return _block_inner_local_simple(step)
    if kind == 2:
        return _block_inner_local_constrained(step)
    if kind == 3:
        return _block_implied_action_chain(step, num_actions)
    if kind == 4:
        return _block_interface_to_implied_chain()
    if kind == 5:
        return _block_implied_chain(2, num_globals)
    if kind == 6:
        return _block_implied_chain(min(5, max_chain_length), num_globals)
    if kind == 7:
        return _block_implied_chain(max_chain_length, num_globals)
    if kind == 8:
        return _block_move_interface()
    if kind == 9:
        return _block_move_interface_chain()
    return _block_comment(step)


def _emit_main_action_header(fqun_path: str, num_actions: int) -> list[str]:
    lines: list[str] = [
        f"define the potential action<{fqun_path}> {{",
        (
            f"{_OUTER_INDENT}it also assigns the"
            f" position<{_short_global_name(_IMPLIED_POSITION_INDEX)}>."
        ),
    ]
    for i in range(num_actions):
        action_name = _short_global_name(i, is_action=True)
        lines.append(f"{_OUTER_INDENT}it also assigns the action<{action_name}>.")
    lines.extend(
        [
            f"{_OUTER_INDENT}define the position<run>.",
            f"{_OUTER_INDENT}define the position<{_INTERFACE_SIMPLE}>.",
            f"{_OUTER_INDENT}define the position<{_INTERFACE_TO_G0}> {{",
            f"{_INNER_INDENT}it may only contain particles where {{",
            (
                f"{_DEEP_INDENT}it has the"
                f" position<{_short_global_name(_IMPLIED_POSITION_INDEX)}>."
            ),
            f"{_INNER_INDENT}}}",
            f"{_OUTER_INDENT}}}",
            f"{_OUTER_INDENT}define the position<{_INTERFACE_TO_G2}> {{",
            f"{_INNER_INDENT}it may only contain particles where {{",
            (
                f"{_DEEP_INDENT}it has the"
                f" position<{_short_global_name(_IMPLIED_INTERFACE_TO_G2_INDEX)}>."
            ),
            f"{_INNER_INDENT}}}",
            f"{_OUTER_INDENT}}}",
            f"{_OUTER_INDENT}define the position<{_INTERFACE_DST}>.",
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
        ]
    )
    return lines


def _emit_main_action_close() -> list[str]:
    return [f"{_OUTER_INDENT}}}", "}", ""]


def generate_source_lines(
    target_lines: int,
    fqun: str = DEFAULT_FQUN,
    max_chain_length: int = DEFAULT_MAX_CHAIN_LENGTH,
) -> list[str]:
    """Return the generated source as a list of lines (no trailing newlines).

    The total line count is at least ``target_lines``. The output mixes
    many definition shapes and statement kinds; ``max_chain_length`` sets
    the longest chained reference produced inside the main action body.
    """
    if target_lines < _MIN_TARGET_LINES:
        raise ValueError(
            f"target_lines must be at least {_MIN_TARGET_LINES}, got {target_lines}"
        )
    if max_chain_length < _MIN_CHAIN_LENGTH:
        raise ValueError(
            f"max_chain_length must be at least {_MIN_CHAIN_LENGTH}, got {max_chain_length}"
        )

    fqun_prefix, _path = _split_fqun(fqun)
    num_globals = max(max_chain_length, 20)
    num_actions = 5
    fqun_destructor = f"{fqun_prefix}:/destructor"
    fqun_main_action = fqun

    lines: list[str] = []
    lines.extend(_emit_header())
    lines.extend(_emit_simple_position_pool(fqun_prefix, num_globals))
    lines.append("")
    lines.extend(_emit_cross_universe_positions())
    lines.extend(_emit_simple_action_pool(fqun_prefix, num_actions))
    lines.extend(_emit_constrained_position(fqun_prefix, num_globals))
    lines.extend(
        _emit_action_with_implications_and_constructor(fqun_prefix, num_globals + 1)
    )
    lines.extend(_emit_main_action_header(fqun_main_action, num_actions))

    close_lines = _emit_main_action_close() + _emit_destructor_action(fqun_destructor)

    step = 0
    while len(lines) + len(close_lines) < target_lines:
        lines.extend(_next_body_block(step, num_globals, num_actions, max_chain_length))
        step += 1

    lines.extend(close_lines)
    return lines


def _iter_with_newlines(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        yield line
        yield "\n"


def write_to_path(
    output: Path,
    target_lines: int,
    fqun: str = DEFAULT_FQUN,
    max_chain_length: int = DEFAULT_MAX_CHAIN_LENGTH,
) -> int:
    """Write generated source to ``output``. Returns the number of lines written."""
    lines = generate_source_lines(
        target_lines, fqun=fqun, max_chain_length=max_chain_length
    )
    with output.open("w", encoding="utf-8") as f:
        for chunk in _iter_with_newlines(lines):
            _ = f.write(chunk)
    return len(lines)


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate a large, syntactically-diverse Define source file."
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the generated .dfn file",
    )
    _ = parser.add_argument(
        "--lines",
        type=int,
        default=DEFAULT_TARGET_LINES,
        help=f"Target number of lines (default: {DEFAULT_TARGET_LINES:,})",
    )
    _ = parser.add_argument(
        "--fqun",
        default=DEFAULT_FQUN,
        help=f"Fully-qualified universe name for the main action (default: {DEFAULT_FQUN})",
    )
    _ = parser.add_argument(
        "--max-chain-length",
        type=int,
        default=DEFAULT_MAX_CHAIN_LENGTH,
        help=(
            "Longest chained reference to emit inside the main action"
            f" (default: {DEFAULT_MAX_CHAIN_LENGTH})"
        ),
    )
    args = parser.parse_args()
    output_path = cast("Path", args.output)
    target_lines = cast("int", args.lines)
    fqun = cast("str", args.fqun)
    max_chain_length = cast("int", args.max_chain_length)
    written = write_to_path(
        output_path,
        target_lines,
        fqun=fqun,
        max_chain_length=max_chain_length,
    )
    print(f"Wrote {written:,} lines to {output_path}")


if __name__ == "__main__":
    main()
