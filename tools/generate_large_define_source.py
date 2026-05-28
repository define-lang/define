"""Generate a large, syntactically-diverse Define source file for stress testing.

Emits a single ``.dfn`` whose contents are accepted by the parser and
transformer (non-filesystem mode). The source exercises a broad slice of
the grammar:

  * A pool of top-level potential position and potential action definitions
    in the same FQUN as the main action, so short-form references from
    inside the main action resolve to defined positions. Each pool
    position declares ``it has the position</g_(i+1)>`` so long chains
    through the pool satisfy the chain-element constraint check.
  * Standalone potential position definitions in 2-part and 3-part FQUN
    forms in other universes, to exercise the multi-format FQUN parser
    path. They are not referenced from the main action because the
    validator's non-filesystem mode currently raises KeyError when
    processing a reference edge to a cross-universe target.
  * Positions with constraint blocks, with quality implications, with
    init blocks, and combinations.
  * Actions with full bodies and a destructor action that triggers on
    ``this particle is being destroyed``.
  * Inside the bulk action: every ``ActionStatement`` kind -- local
    position definitions (simple and constrained), ``create``, ``move``,
    and ``destroy`` -- using a mix of local references, short global
    references (``</path>``), a full-FQUN reference, and chained
    references including very long chains (up to the configured maximum).
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
    # an already-defined name. The non-filesystem validator skips
    # DiscoveredFile creation for same-source back-references; forward
    # references would instead trigger NoProjectRootInNonFilesystemContext.
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
        lines.extend(
            [
                f"define the potential action<{name}> {{",
                f"{_OUTER_INDENT}define the position<run>.",
                f"{_OUTER_INDENT}define the position<_noop>.",
                f"{_OUTER_INDENT}it happens when {{",
                f"{_INNER_INDENT}the position<run> has a particle.",
                f"{_OUTER_INDENT}}} and it does {{",
                f"{_INNER_INDENT}create a particle in position<_noop>.",
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


def _emit_position_with_implications_and_init(prefix: str, index: int) -> list[str]:
    name = _qualified_global_name(prefix, index)
    return [
        f"define the potential position<{name}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{_short_global_name(0)}>.",
        f"{_OUTER_INDENT}it also assigns the action<{_short_global_name(1, is_action=True)}>.",
        f"{_OUTER_INDENT}it may only contain particles where {{",
        f"{_INNER_INDENT}it has the position<{_short_global_name(2)}>.",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}after it is assigned {{",
        f"{_INNER_INDENT}create a particle in position<{_short_global_name(0)}>.",
        f"{_INNER_INDENT}# Trailing comment in init block",
        (
            f"{_INNER_INDENT}create a particle in"
            f" action<{_short_global_name(1, is_action=True)}>::position<_noop>."
        ),
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


def _chained_create_statement(chain_length: int, num_globals: int) -> str:
    elements = [
        f"position<{_short_global_name(i % num_globals)}>" for i in range(chain_length)
    ]
    chain = "::".join(elements)
    return f"{_INNER_INDENT}create a particle in {chain}."


def _next_body_statement(
    step: int, num_globals: int, num_actions: int, max_chain_length: int
) -> str:
    """Return a single body line, cycling through statement kinds by ``step``."""
    kind = step % 12
    if kind == 0:
        return f"{_INNER_INDENT}create a particle in position<local_a>."
    if kind == 1:
        # Only g_0 is brought into the main action's scope via ``it also
        # assigns``; non-chained references to other pool positions would
        # trigger UnknownGlobalNameDiagnostic.
        return f"{_INNER_INDENT}create a particle in position<{_short_global_name(0)}>."
    if kind == 2:
        return _chained_create_statement(2, num_globals)
    if kind == 3:
        return _chained_create_statement(min(5, max_chain_length), num_globals)
    if kind == 4:
        return _chained_create_statement(max_chain_length, num_globals)
    if kind == 5:
        # local_a is constrained to ``it has the position</g_0>``, so the
        # local+global chain pins to g_0 to satisfy that constraint.
        return (
            f"{_INNER_INDENT}create a particle in"
            f" position<local_a>::position<{_short_global_name(0)}>."
        )
    if kind == 6:
        ai = step % num_actions
        return (
            f"{_INNER_INDENT}create a particle in"
            f" action<{_short_global_name(ai, is_action=True)}>::position<_noop>."
        )
    if kind == 7:
        return (
            f"{_INNER_INDENT}move the particle in position<local_a>"
            " to position<local_b>."
        )
    if kind == 8:
        # See kind 5: local_a's constraint pins the second element to g_0.
        return (
            f"{_INNER_INDENT}move the particle in"
            f" position<local_a>::position<{_short_global_name(0)}>"
            f" to position<local_b>."
        )
    if kind == 9:
        return f"{_INNER_INDENT}destroy the particle in position<local_b>."
    if kind == 10:
        return f"{_INNER_INDENT}# cycle marker {step}"
    return f"{_INNER_INDENT}define the position<scratch_{step}>."


def _emit_main_action_header(fqun_path: str, num_actions: int) -> list[str]:
    lines: list[str] = [
        f"define the potential action<{fqun_path}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{_short_global_name(0)}>.",
    ]
    for i in range(num_actions):
        action_name = _short_global_name(i, is_action=True)
        lines.append(f"{_OUTER_INDENT}it also assigns the action<{action_name}>.")
    lines.extend(
        [
            f"{_OUTER_INDENT}define the position<run>.",
            f"{_OUTER_INDENT}define the position<local_a> {{",
            f"{_INNER_INDENT}it may only contain particles where {{",
            f"{_DEEP_INDENT}it has the position<{_short_global_name(0)}>.",
            f"{_INNER_INDENT}}}",
            f"{_OUTER_INDENT}}}",
            f"{_OUTER_INDENT}define the position<local_b>.",
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
        _emit_position_with_implications_and_init(fqun_prefix, num_globals + 1)
    )
    lines.extend(_emit_main_action_header(fqun_main_action, num_actions))

    close_lines = _emit_main_action_close() + _emit_destructor_action(fqun_destructor)

    step = 0
    while len(lines) + len(close_lines) < target_lines:
        lines.append(
            _next_body_statement(step, num_globals, num_actions, max_chain_length)
        )
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
