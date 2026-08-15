"""Generate a Define source file whose bodies stress the operation graph.

Emits a single ``.dfn`` that compiles to zero diagnostics through the
non-filesystem validator, shaped so that the dominant validation work is
building each action's operation dependency graph (the spec's
"Deterministic Automatic Concurrency" rules) rather than parsing or the
reference-graph traversal.

The other profiling generators leave most of those rules cold: the
single-large-action source is create/destroy dominated with only a
handful of trivial moves, and the dense action call graph source
contains no move statements at all. This source is built from repeating
statement families, each aimed at a specific dependency rule:

  * A move ladder: one particle moved through ``move_chain_length``
    positions, so every move's dependencies come from the previous move.
  * A deep position chain filled under ``tree_src`` and then moved to
    ``tree_dst`` in one move, so the move must reduce its dependencies to
    the deepest operated-on child position. Alternate repetitions destroy
    the moved-to chain child-by-child (each destroy finding the move as
    the most recent operation on its parent names) or in one cascade.
  * A wide particle with ``wide_children`` child positions all operated
    on before the whole particle moves, so the move's child-operation
    snapshot has to filter many independent child operations.
  * A sibling move ladder that shuffles one particle across the child
    positions of a single parent particle, hitting the rule that drops a
    move's target-side dependency when its source-side dependencies
    already reach it.
  * Many pairs of independent Move Particle Statements, all preceded by
    the same long Move chain. Each pair remains required by a separate
    Destroy Particle Statement, so dependency comparison must repeatedly
    distinguish a common dependency path from reachability between the
    pair.
  * A per-repetition contracted position that is first referenced through
    a chained create (inferring an occupied Action Requirement) and then
    destroyed while child positions on two separate paths were operated
    on, so emptying it needs the caller-contribution bookkeeping for a
    required particle's children.
  * Pod positions that trigger a ``worker`` action (which moves its
    ``input`` to ``out``) and a ``sink`` action (which destroys its
    ``input``'s child and then ``input``). The body then moves the
    worker's guaranteed ``out`` to a local position, so caller operations
    depend on Action Guarantees, and re-triggers each pod
    ``retriggers`` times before destroying it.

Definitions are emitted before their referents so every reference is a
back-reference; in non-filesystem mode a forward reference to a
same-source name raises before any diagnostic.

Run via:
    bazelisk run --noshow_progress --ui_event_filters=-info //tools/generators:generate_operation_graph_source -- --output /tmp/og.dfn
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:operation_graph"
DEFAULT_REPETITIONS = 700
DEFAULT_MOVE_CHAIN_LENGTH = 24
DEFAULT_TREE_DEPTH = 32
DEFAULT_WIDE_CHILDREN = 48
DEFAULT_PODS = 4
DEFAULT_RETRIGGERS = 2
DEFAULT_INDEPENDENT_MOVE_BRANCHES = 1024
DEFAULT_INDEPENDENT_MOVE_CHAIN_LENGTH = 1024

_MIN_REPETITIONS = 1
_MIN_MOVE_CHAIN_LENGTH = 2
_MIN_TREE_DEPTH = 2
_MIN_WIDE_CHILDREN = 2
_MIN_PODS = 0
_MIN_RETRIGGERS = 1
_MIN_INDEPENDENT_MOVE_BRANCHES = 2
_MIN_INDEPENDENT_MOVE_CHAIN_LENGTH = 2
_OUTER_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "

_ITEM = "/item"
_INDEPENDENT_LEFT = "/independent_left"
_INDEPENDENT_RIGHT = "/independent_right"


def _depth_path(i: int) -> str:
    return f"/depth_{i}"


def _child_path(i: int) -> str:
    return f"/child_{i}"


def _independent_box_path(i: int) -> str:
    return f"/independent_box_{i}"


def _qualified(prefix: str, path: str) -> str:
    return f"{prefix}:{path}"


def _emit_header() -> list[str]:
    return [
        "# Generated Define source. Stresses operation graph construction.",
        "",
    ]


def _emit_position_pools(prefix: str, tree_depth: int, wide_children: int) -> list[str]:
    lines = [f"define the potential position<{_qualified(prefix, _ITEM)}>."]
    # The deepest chain position is emitted first so each constraint is a
    # back-reference to an already-defined name.
    for i in reversed(range(tree_depth)):
        name = _qualified(prefix, _depth_path(i))
        if i == tree_depth - 1:
            lines.append(f"define the potential position<{name}>.")
            continue
        lines.extend(
            [
                f"define the potential position<{name}> {{",
                f"{_OUTER_INDENT}it may only contain particles where {{",
                f"{_INNER_INDENT}it has the position<{_depth_path(i + 1)}>.",
                f"{_OUTER_INDENT}}}",
                "}",
            ]
        )
    for i in range(wide_children):
        name = _qualified(prefix, _child_path(i))
        lines.append(f"define the potential position<{name}>.")
    lines.append("")
    return lines


def _emit_independent_move_branch_positions(
    prefix: str, independent_move_branches: int
) -> list[str]:
    if independent_move_branches == 0:
        return []
    lines = [
        f"define the potential position<{_qualified(prefix, _INDEPENDENT_LEFT)}>.",
        f"define the potential position<{_qualified(prefix, _INDEPENDENT_RIGHT)}>.",
    ]
    for branch in range(independent_move_branches):
        lines.extend(
            [
                f"define the potential position<{_qualified(prefix, _independent_box_path(branch))}> {{",
                f"{_OUTER_INDENT}it may only contain particles where {{",
                f"{_INNER_INDENT}it has the position<{_INDEPENDENT_LEFT}>.",
                f"{_INNER_INDENT}it has the position<{_INDEPENDENT_RIGHT}>.",
                f"{_OUTER_INDENT}}}",
                "}",
            ]
        )
    lines.append("")
    return lines


def _emit_worker_action(prefix: str) -> list[str]:
    name = _qualified(prefix, "/worker")
    return [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}define the position<trigger_pos>.",
        f"{_OUTER_INDENT}define the position<input> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_ITEM}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        # ``out`` requires the particle to have ``/item`` so the move below
        # is what requires ``input``'s constraint, keeping it live.
        f"{_OUTER_INDENT}define the position<out> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_ITEM}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<trigger_pos> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        # Emptying a caller-filled contracted position infers an occupied
        # Action Requirement, and filling ``out`` records the Action
        # Guarantee the caller's body consumes.
        f"{_INNER_INDENT}move the particle in position<input> to position<out>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_sink_action(prefix: str) -> list[str]:
    name = _qualified(prefix, "/sink")
    return [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}define the position<trigger_pos>.",
        f"{_OUTER_INDENT}define the position<input> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_ITEM}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<trigger_pos> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        # Destroying a caller-created child and then its parent makes the
        # caller's child operations part of this action's requirement
        # dependencies.
        f"{_INNER_INDENT}destroy the particle in position<input>::position<{_ITEM}>.",
        f"{_INNER_INDENT}destroy the particle in position<input>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_constrained_interface(
    name: str, constraint_paths: list[str], *, is_action: bool = False
) -> list[str]:
    kind = "action" if is_action else "position"
    lines = [
        f"{_OUTER_INDENT}define the position<{name}> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
    ]
    for path in constraint_paths:
        lines.append(f"{_DEEP_INDENT}it has the {kind}<{path}>.")
    lines.extend(
        [
            f"{_INNER_INDENT}}}",
            f"{_OUTER_INDENT}}}",
        ]
    )
    return lines


def _create(reference: str) -> str:
    return f"{_INNER_INDENT}create a particle in {reference}."


def _destroy(reference: str) -> str:
    return f"{_INNER_INDENT}destroy the particle in {reference}."


def _move(source: str, target: str) -> str:
    return f"{_INNER_INDENT}move the particle in {source} to {target}."


def _block_move_ladder(move_chain_length: int) -> list[str]:
    lines = [_create("position<rung_0>")]
    for i in range(move_chain_length - 1):
        lines.append(_move(f"position<rung_{i}>", f"position<rung_{i + 1}>"))
    lines.append(_destroy(f"position<rung_{move_chain_length - 1}>"))
    return lines


def _tree_chain(head: str, depth: int) -> str:
    elements = [f"position<{head}>"]
    elements.extend(f"position<{_depth_path(i)}>" for i in range(depth))
    return "::".join(elements)


def _block_deep_tree(tree_depth: int, step: int) -> list[str]:
    lines = [_create("position<tree_src>")]
    # The chain rule requires every position in a chain except the last to
    # already contain a particle, so the chain is filled top-down.
    for depth in range(1, tree_depth + 1):
        lines.append(_create(_tree_chain("tree_src", depth)))
    lines.append(_move("position<tree_src>", "position<tree_dst>"))
    if step % 2 == 0:
        # Child-by-child destruction: each destroy's most recent operation
        # on its parent names is the move, exercising the stale-chain
        # reduction after a move refills a whole chain.
        for depth in range(tree_depth, 0, -1):
            lines.append(_destroy(_tree_chain("tree_dst", depth)))
    lines.append(_destroy("position<tree_dst>"))
    return lines


def _block_wide_fan(wide_children: int, step: int) -> list[str]:
    lines = [_create("position<wide_src>")]
    for i in range(wide_children):
        lines.append(_create(f"position<wide_src>::position<{_child_path(i)}>"))
    lines.append(_move("position<wide_src>", "position<wide_dst>"))
    if step % 2 == 0:
        for i in range(wide_children):
            lines.append(_destroy(f"position<wide_dst>::position<{_child_path(i)}>"))
    lines.append(_destroy("position<wide_dst>"))
    return lines


def _block_sibling_ladder(wide_children: int) -> list[str]:
    lines = [
        _create("position<side>"),
        _create(f"position<side>::position<{_child_path(0)}>"),
    ]
    # Every move after the first gets its target-side dependency from an
    # operation on the shared parent particle that its source-side
    # dependencies already reach, exercising the dependency-deduplication
    # rule for moves.
    for i in range(wide_children - 1):
        lines.append(
            _move(
                f"position<side>::position<{_child_path(i)}>",
                f"position<side>::position<{_child_path(i + 1)}>",
            )
        )
    lines.append(_destroy("position<side>"))
    return lines


def _block_independent_move_branches(
    independent_move_branches: int,
    independent_move_chain_length: int,
) -> list[str]:
    lines = [_create("position<independent_source>")]
    preceding_position = "position<independent_source>"
    for move_index in range(independent_move_chain_length - 2):
        next_position = f"position<independent_stage_{move_index}>"
        lines.append(_move(preceding_position, next_position))
        preceding_position = next_position
    lines.extend(
        [
            _move(preceding_position, "position<independent_workspace>"),
            _move(
                "position<independent_workspace>",
                "position<independent_moved_marker>",
            ),
            _create("position<independent_workspace>"),
        ]
    )

    for branch in range(independent_move_branches):
        box = f"position<independent_workspace>::position<{_independent_box_path(branch)}>"
        lines.extend(
            [
                _create(box),
                _create(f"{box}::position<{_INDEPENDENT_LEFT}>"),
                _create(f"{box}::position<{_INDEPENDENT_RIGHT}>"),
                _move(
                    f"{box}::position<{_INDEPENDENT_LEFT}>",
                    f"position<independent_left_holder_{branch}>",
                ),
                _move(
                    f"{box}::position<{_INDEPENDENT_RIGHT}>",
                    f"position<independent_right_holder_{branch}>",
                ),
                _destroy(box),
                _destroy(f"position<independent_left_holder_{branch}>"),
                _destroy(f"position<independent_right_holder_{branch}>"),
            ]
        )
    lines.extend(
        [
            _destroy("position<independent_workspace>"),
            _destroy("position<independent_moved_marker>"),
        ]
    )
    return lines


def _block_requirement_children(step: int) -> list[str]:
    depth_chain = f"position<req_{step}>::position<{_depth_path(0)}>"
    # The first reference chains through the untouched contracted position,
    # inferring an occupied Action Requirement on it. The later destroy then
    # empties a required particle whose child positions were operated on
    # along two separate paths.
    return [
        _create(depth_chain),
        _create(f"{depth_chain}::position<{_depth_path(1)}>"),
        _create(f"position<req_{step}>::position<{_child_path(0)}>"),
        _destroy(f"position<req_{step}>"),
    ]


def _block_worker_pod(pod: int, retriggers: int) -> list[str]:
    chain = f"position<wpod_{pod}>::action</worker>"
    lines = [_create(f"position<wpod_{pod}>")]
    for round_index in range(retriggers):
        if round_index > 0:
            lines.append(_destroy(f"{chain}::position<trigger_pos>"))
        lines.extend(
            [
                _create(f"{chain}::position<input>"),
                _create(f"{chain}::position<input>::position<{_ITEM}>"),
                _create(f"{chain}::position<trigger_pos>"),
                # The worker guarantees ``out``; moving it makes this body
                # depend on the Action Guarantee rather than on the trigger.
                _move(f"{chain}::position<out>", "position<result>"),
                _destroy("position<result>"),
            ]
        )
    lines.append(_destroy(f"position<wpod_{pod}>"))
    return lines


def _block_sink_pod(pod: int, retriggers: int) -> list[str]:
    chain = f"position<spod_{pod}>::action</sink>"
    lines = [_create(f"position<spod_{pod}>")]
    for round_index in range(retriggers):
        if round_index > 0:
            lines.append(_destroy(f"{chain}::position<trigger_pos>"))
        lines.extend(
            [
                _create(f"{chain}::position<input>"),
                _create(f"{chain}::position<input>::position<{_ITEM}>"),
                _create(f"{chain}::position<trigger_pos>"),
            ]
        )
    lines.append(_destroy(f"position<spod_{pod}>"))
    return lines


def _emit_main_action_header(
    prefix: str,
    repetitions: int,
    move_chain_length: int,
    wide_children: int,
    pods: int,
    independent_move_branches: int,
    independent_move_chain_length: int,
) -> list[str]:
    name = _qualified(prefix, "/test")
    all_children = [_child_path(i) for i in range(wide_children)]
    lines = [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}define the position<run>.",
    ]
    if pods > 0:
        lines.append(f"{_OUTER_INDENT}define the position<result>.")
    for i in range(move_chain_length):
        lines.append(f"{_OUTER_INDENT}define the position<rung_{i}>.")
    lines.extend(_emit_constrained_interface("tree_src", [_depth_path(0)]))
    lines.extend(_emit_constrained_interface("tree_dst", [_depth_path(0)]))
    lines.extend(_emit_constrained_interface("wide_src", all_children))
    lines.extend(_emit_constrained_interface("wide_dst", all_children))
    lines.extend(_emit_constrained_interface("side", all_children))
    if independent_move_branches > 0:
        independent_boxes = [
            _independent_box_path(branch) for branch in range(independent_move_branches)
        ]
        lines.extend(
            _emit_constrained_interface("independent_source", independent_boxes)
        )
        lines.extend(
            _emit_constrained_interface("independent_workspace", independent_boxes)
        )
        lines.append(f"{_OUTER_INDENT}define the position<independent_moved_marker>.")
        for move_index in range(independent_move_chain_length - 2):
            lines.append(
                f"{_OUTER_INDENT}define the position<independent_stage_{move_index}>."
            )
        for branch in range(independent_move_branches):
            lines.extend(
                [
                    f"{_OUTER_INDENT}define the position<independent_left_holder_{branch}>.",
                    f"{_OUTER_INDENT}define the position<independent_right_holder_{branch}>.",
                ]
            )
    for step in range(repetitions):
        lines.extend(
            _emit_constrained_interface(f"req_{step}", [_depth_path(0), _child_path(0)])
        )
    for pod in range(pods):
        lines.extend(
            _emit_constrained_interface(f"wpod_{pod}", ["/worker"], is_action=True)
        )
        lines.extend(
            _emit_constrained_interface(f"spod_{pod}", ["/sink"], is_action=True)
        )
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
        ]
    )
    return lines


def _emit_main_action_close() -> list[str]:
    return [f"{_OUTER_INDENT}}}", "}", ""]


def _emit_entry_constructor(prefix: str) -> list[str]:
    # Code generation requires a constructor entry point; the interesting
    # work stays in the trigger-position-driven main action.
    name = _qualified(prefix, "/boot")
    return [
        f"define the potential action<{name}> {{",
        f"{_OUTER_INDENT}define the position<_noop>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is created.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<_noop>.",
        f"{_INNER_INDENT}destroy the particle in position<_noop>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def generate_source_lines(
    repetitions: int = DEFAULT_REPETITIONS,
    move_chain_length: int = DEFAULT_MOVE_CHAIN_LENGTH,
    tree_depth: int = DEFAULT_TREE_DEPTH,
    wide_children: int = DEFAULT_WIDE_CHILDREN,
    pods: int = DEFAULT_PODS,
    retriggers: int = DEFAULT_RETRIGGERS,
    independent_move_branches: int = DEFAULT_INDEPENDENT_MOVE_BRANCHES,
    independent_move_chain_length: int = DEFAULT_INDEPENDENT_MOVE_CHAIN_LENGTH,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Return the generated source as a list of lines (no trailing newlines).

    The main action's body repeats the statement families ``repetitions``
    times; every family leaves each reused position in the state the next
    repetition expects, so repetitions compose cleanly.
    """
    if repetitions < _MIN_REPETITIONS:
        raise ValueError(
            f"repetitions must be at least {_MIN_REPETITIONS}, got {repetitions}"
        )
    if move_chain_length < _MIN_MOVE_CHAIN_LENGTH:
        raise ValueError(
            f"move_chain_length must be at least {_MIN_MOVE_CHAIN_LENGTH},"
            + f" got {move_chain_length}"
        )
    if tree_depth < _MIN_TREE_DEPTH:
        raise ValueError(
            f"tree_depth must be at least {_MIN_TREE_DEPTH}, got {tree_depth}"
        )
    if wide_children < _MIN_WIDE_CHILDREN:
        raise ValueError(
            f"wide_children must be at least {_MIN_WIDE_CHILDREN}, got {wide_children}"
        )
    if pods < _MIN_PODS:
        raise ValueError(f"pods must be at least {_MIN_PODS}, got {pods}")
    if retriggers < _MIN_RETRIGGERS:
        raise ValueError(
            f"retriggers must be at least {_MIN_RETRIGGERS}, got {retriggers}"
        )
    if independent_move_branches < 0 or independent_move_branches == 1:
        raise ValueError(
            "independent_move_branches must be zero or at least"
            + f" {_MIN_INDEPENDENT_MOVE_BRANCHES}, got {independent_move_branches}"
        )
    if (
        independent_move_branches > 0
        and independent_move_chain_length < _MIN_INDEPENDENT_MOVE_CHAIN_LENGTH
    ):
        raise ValueError(
            "independent_move_chain_length must be at least"
            + f" {_MIN_INDEPENDENT_MOVE_CHAIN_LENGTH},"
            + f" got {independent_move_chain_length}"
        )

    lines: list[str] = []
    lines.extend(_emit_header())
    lines.extend(_emit_position_pools(fqun_prefix, tree_depth, wide_children))
    lines.extend(
        _emit_independent_move_branch_positions(fqun_prefix, independent_move_branches)
    )
    if pods > 0:
        lines.extend(_emit_worker_action(fqun_prefix))
        lines.extend(_emit_sink_action(fqun_prefix))
    lines.extend(
        _emit_main_action_header(
            fqun_prefix,
            repetitions,
            move_chain_length,
            wide_children,
            pods,
            independent_move_branches,
            independent_move_chain_length,
        )
    )
    if independent_move_branches > 0:
        lines.append(f"{_INNER_INDENT}# independent Move branches")
        lines.extend(
            _block_independent_move_branches(
                independent_move_branches,
                independent_move_chain_length,
            )
        )
    for step in range(repetitions):
        lines.append(f"{_INNER_INDENT}# repetition {step}")
        lines.extend(_block_move_ladder(move_chain_length))
        lines.extend(_block_deep_tree(tree_depth, step))
        lines.extend(_block_wide_fan(wide_children, step))
        lines.extend(_block_sibling_ladder(wide_children))
        lines.extend(_block_requirement_children(step))
        for pod in range(pods):
            lines.extend(_block_worker_pod(pod, retriggers))
            lines.extend(_block_sink_pod(pod, retriggers))
    lines.extend(_emit_main_action_close())
    lines.extend(_emit_entry_constructor(fqun_prefix))
    return lines


def write_to_path(
    output: Path,
    repetitions: int = DEFAULT_REPETITIONS,
    move_chain_length: int = DEFAULT_MOVE_CHAIN_LENGTH,
    tree_depth: int = DEFAULT_TREE_DEPTH,
    wide_children: int = DEFAULT_WIDE_CHILDREN,
    pods: int = DEFAULT_PODS,
    retriggers: int = DEFAULT_RETRIGGERS,
    independent_move_branches: int = DEFAULT_INDEPENDENT_MOVE_BRANCHES,
    independent_move_chain_length: int = DEFAULT_INDEPENDENT_MOVE_CHAIN_LENGTH,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> int:
    """Write generated source to ``output``. Returns the number of lines written."""
    lines = generate_source_lines(
        repetitions=repetitions,
        move_chain_length=move_chain_length,
        tree_depth=tree_depth,
        wide_children=wide_children,
        pods=pods,
        retriggers=retriggers,
        independent_move_branches=independent_move_branches,
        independent_move_chain_length=independent_move_chain_length,
        fqun_prefix=fqun_prefix,
    )
    return generator_io.write_lines(output, lines)


@click.command()
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--repetitions",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_REPETITIONS,
    show_default=True,
    help="Times the statement families repeat in the main action body.",
)
@click.option(
    "--move-chain-length",
    type=click.IntRange(min=_MIN_MOVE_CHAIN_LENGTH),
    default=DEFAULT_MOVE_CHAIN_LENGTH,
    show_default=True,
    help="Positions each move-ladder particle passes through.",
)
@click.option(
    "--tree-depth",
    type=click.IntRange(min=_MIN_TREE_DEPTH),
    default=DEFAULT_TREE_DEPTH,
    show_default=True,
    help="Depth of the position chain moved in one move.",
)
@click.option(
    "--wide-children",
    type=click.IntRange(min=_MIN_WIDE_CHILDREN),
    default=DEFAULT_WIDE_CHILDREN,
    show_default=True,
    help="Child positions operated on before their parent particle moves.",
)
@click.option(
    "--pods",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_PODS,
    show_default=True,
    help="Worker and sink pods triggered per repetition.",
)
@click.option(
    "--retriggers",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_RETRIGGERS,
    show_default=True,
    help="Trigger rounds per pod per repetition.",
)
@click.option(
    "--independent-move-branches",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_INDEPENDENT_MOVE_BRANCHES,
    show_default=True,
    help="Independent Move dependency pairs sharing one Move chain; zero omits them.",
)
@click.option(
    "--independent-move-chain-length",
    type=click.IntRange(min=_MIN_INDEPENDENT_MOVE_CHAIN_LENGTH),
    default=DEFAULT_INDEPENDENT_MOVE_CHAIN_LENGTH,
    show_default=True,
    help="Moves in the chain preceding every independent dependency pair.",
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(
    output: Path,
    repetitions: int,
    move_chain_length: int,
    tree_depth: int,
    wide_children: int,
    pods: int,
    retriggers: int,
    independent_move_branches: int,
    independent_move_chain_length: int,
    fqun_prefix: str,
):
    """Generate a Define source file whose bodies stress the operation graph.

    Emits one .dfn whose action body repeats statement families, each aimed at a
    specific operation dependency rule: a move ladder, a deep position chain moved
    at once and destroyed child by child, a wide particle whose operated-on child
    positions must be filtered into a move's child-operation snapshot, a sibling
    move ladder under one parent particle, independent Move pairs with the same
    preceding Move chain, and worker pods whose Action Guarantees the body consumes.
    The other profiling sources contain few or no move statements, so this is the
    shape that warms operation-graph construction.

    Scale it with --repetitions for body length; --tree-depth makes the
    ancestor-chain walk quadratically more expensive. Scale
    --independent-move-branches and --independent-move-chain-length together to
    increase the repeated dependency-comparison work. The generated source validates
    to zero diagnostics.
    """
    written = generator_cli.invoke(
        lambda: write_to_path(
            output,
            repetitions=repetitions,
            move_chain_length=move_chain_length,
            tree_depth=tree_depth,
            wide_children=wide_children,
            pods=pods,
            retriggers=retriggers,
            independent_move_branches=independent_move_branches,
            independent_move_chain_length=independent_move_chain_length,
            fqun_prefix=fqun_prefix,
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
