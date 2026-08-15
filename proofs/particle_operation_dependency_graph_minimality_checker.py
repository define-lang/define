"""Brute-force checker for the Particle Operation Dependency Graph rules.

This checker implements the specification's Fill Rule, Empty Rule (Collection,
Comparison, Move Correction), Move Rule (with the Fill Dependency removal), and
Action Parent Rule directly from the rule text in ``define/spec/spec.md``, over
exhaustively and randomly generated valid operation sequences on kinded
position trees. It is independent of the compiler's implementation.

At every operation of every generated sequence it verifies the claims of
``particle-operation-dependency-graph-minimality-proof.md``:

1. The final dependency set is a reachability antichain, so the graph stays
   transitively reduced (the Incremental Reduction Theorem).
2. Every operation reaches every candidate in its Collection (statement 3 of
   the proof's invariants).
3. A later operation reaches every earlier operation on a related position
   (statement 1).
4. Every dependency edge connects operations on related positions (the
   direct-dependency position lemma).
5. Four readings of the rules produce identical dependency sets: the
   specification's Collection over existing positions, the particle-tracked
   Collection, the Collection augmented with entries at position names that no
   longer refer to a position (the reading assumed by the Lean model's
   ``latest_source_candidate``), and the Move Rule applied to the finished
   Empty Rule result instead of the raw Collection.

Run with ``uv run``:

    uv run proofs/particle_operation_dependency_graph_minimality_checker.py

The default run starts with a self-test that disables the Move Correction and
the Fill Dependency removal in turn and confirms that the checker then reports
the known counterexample families. A checker that cannot detect the violations
it hunts would give false confidence.
"""

from __future__ import annotations

import random
import sys
import time
import typing
from dataclasses import dataclass

import click

_CREATE = "C"
_DESTROY = "D"
_MOVE = "M"

# A position with this kind accepts particles of any kind, like a position
# defined with no Position Constraint Block.
_UNCONSTRAINED = -1
# Particles created in an unconstrained position get no qualities and therefore
# define no child positions.
_BARE = 99


@dataclass(frozen=True)
class _WorldConfig:
    """A tree of position kinds and the top-level positions of an action."""

    name: str
    # kind -> child position definitions as (child name, child kind)
    kinds: dict[int, tuple[tuple[str, int], ...]]
    # top-level position name -> kind
    top: tuple[tuple[str, int], ...]


_CONFIGS = [
    _WorldConfig(
        "two_tops_one_child",
        {0: (("a", 1),), 1: (), _BARE: ()},
        (("p", 0), ("q", 0)),
    ),
    _WorldConfig(
        "cross_depth",
        {0: (("a", 1), ("b", 1)), 1: (), _BARE: ()},
        (("p", 0), ("q", 0), ("r", 1)),
    ),
    _WorldConfig(
        "depth_three",
        {0: (("a", 1),), 1: (("c", 2),), 2: (), _BARE: ()},
        (("p", 0), ("q", 1), ("r", 2)),
    ),
    _WorldConfig(
        "depth_three_wide",
        {0: (("a", 1), ("b", 1)), 1: (("c", 2),), 2: (), _BARE: ()},
        (("p", 0), ("q", 1), ("r", 2), ("w", 2)),
    ),
    _WorldConfig(
        "unconstrained_holders",
        {0: (("a", 1), ("b", 1)), 1: (), _BARE: ()},
        (("p", 0), ("u", _UNCONSTRAINED), ("v", _UNCONSTRAINED)),
    ),
    _WorldConfig(
        "deep_unconstrained",
        {0: (("a", 1),), 1: (("c", _UNCONSTRAINED),), 2: (), _BARE: ()},
        (("p", 0), ("q", 1), ("u", _UNCONSTRAINED)),
    ),
    # The shape of the move_excludes_create_fill_dependency regression tests.
    _WorldConfig(
        "box_shape",
        {0: (("item", 1), ("dest", 2)), 1: (("pay", 2),), 2: (), _BARE: ()},
        (("box", 0), ("holder", 1), ("spare", 2)),
    ),
    # The shape of the parent-move-chain regression tests.
    _WorldConfig(
        "four_tops",
        {0: (("item", 1),), 1: (), _BARE: ()},
        (("p", 0), ("q", 0), ("r", 0), ("w", 0)),
    ),
]


@dataclass(frozen=True)
class _Operation:
    """One Particle Operation; ``second`` is empty except for a Move's target."""

    kind: str
    first: tuple[str, ...]
    second: tuple[str, ...] = ()

    @property
    def positions(self) -> tuple[tuple[str, ...], ...]:
        if self.kind == _MOVE:
            return (self.first, self.second)
        return (self.first,)

    @typing.override
    def __str__(self):
        def chained(name: tuple[str, ...]) -> str:
            return "::".join(name)

        if self.kind == _CREATE:
            return f"create({chained(self.first)})"
        if self.kind == _DESTROY:
            return f"destroy({chained(self.first)})"
        return f"move({chained(self.first)}, {chained(self.second)})"


def _related(one: tuple[str, ...], other: tuple[str, ...]) -> bool:
    shared_depth = min(len(one), len(other))
    return one[:shared_depth] == other[:shared_depth]


def _operations_related(one: _Operation, other: _Operation) -> bool:
    for first_position in one.positions:
        for second_position in other.positions:
            if _related(first_position, second_position):
                return True
    return False


_SPECIFIED = "specified"
_TRACKED = "tracked"
_AUGMENTED = "augmented"

type _UndoValues = list[tuple[tuple[str, ...], int | None]]
type _UndoRecord = tuple[_UndoValues, _UndoValues, _UndoValues]
type _ModelResults = tuple[frozenset[int], frozenset[int], frozenset[int]]


class _RuleState:
    """One growing operation sequence with its dependency graph.

    ``entries`` is the per-name most-recent-entry map from the proof: Creates
    and Destroys write their position, and a Move writes its source, its
    target, and every transitive child position of the moved particle.
    ``arrival`` records when each occupied name last changed occupant, which
    the particle-tracked Collection uses to skip entries from a previous
    occupant era.
    """

    # Mutant subclasses in the self-test disable these to prove the checker
    # detects the violations each correction exists to prevent.
    apply_move_correction: bool = True
    apply_fill_dependency_removal: bool = True

    def __init__(self, config: _WorldConfig):
        self.config: _WorldConfig = config
        self.top_kinds: dict[str, int] = dict(config.top)
        self.occupants: dict[tuple[str, ...], int] = {}
        self.entries: dict[tuple[str, ...], int] = {}
        self.arrival: dict[tuple[str, ...], int] = {}
        self.operations: list[_Operation] = []
        self.dependencies: list[frozenset[int]] = []
        self.reachable: list[int] = []

    def position_kind(self, name: tuple[str, ...]) -> int:
        if len(name) == 1:
            return self.top_kinds[name[0]]
        return dict(self.config.kinds[self.occupants[name[:-1]]])[name[-1]]

    def defined_names(self) -> list[tuple[str, ...]]:
        result: list[tuple[str, ...]] = []

        def walk(name: tuple[str, ...]):
            result.append(name)
            kind = self.occupants.get(name)
            if kind is None:
                return
            for child, _ in self.config.kinds[kind]:
                walk((*name, child))

        for top_name, _ in self.config.top:
            walk((top_name,))
        return result

    def defined_strict_descendants(
        self, name: tuple[str, ...]
    ) -> list[tuple[str, ...]]:
        result: list[tuple[str, ...]] = []

        def walk(walked: tuple[str, ...]):
            kind = self.occupants.get(walked)
            if kind is None:
                return
            for child, _ in self.config.kinds[kind]:
                child_name = (*walked, child)
                result.append(child_name)
                walk(child_name)

        walk(name)
        return result

    def valid_operations(self) -> list[_Operation]:
        result: list[_Operation] = []
        defined = self.defined_names()
        for name in defined:
            if name not in self.occupants:
                result.append(_Operation(_CREATE, name))
        for name, kind in self.occupants.items():
            child_occupied = any(
                (*name, child) in self.occupants for child, _ in self.config.kinds[kind]
            )
            if not child_occupied:
                result.append(_Operation(_DESTROY, name))
        for source, kind in self.occupants.items():
            for target in defined:
                if target in self.occupants or _related(source, target):
                    continue
                target_kind = self.position_kind(target)
                if target_kind != _UNCONSTRAINED and target_kind != kind:
                    continue
                result.append(_Operation(_MOVE, source, target))
        return result

    def created_kind(self, name: tuple[str, ...]) -> int:
        kind = self.position_kind(name)
        return _BARE if kind == _UNCONSTRAINED else kind

    def fill_candidate(self, target: tuple[str, ...]) -> int | None:
        best: int | None = None
        for depth in range(1, len(target) + 1):
            entry = self.entries.get(target[:depth])
            if entry is not None and (best is None or entry > best):
                best = entry
        return best

    def era(self, name: tuple[str, ...]) -> int:
        best = -1
        for depth in range(1, len(name) + 1):
            prefix = name[:depth]
            if prefix in self.occupants and self.arrival[prefix] > best:
                best = self.arrival[prefix]
        return best

    def empty_collection(self, source: tuple[str, ...], model: str) -> set[int]:
        collected: set[int] = set()
        for depth in range(1, len(source) + 1):
            entry = self.entries.get(source[:depth])
            if entry is not None:
                collected.add(entry)
        if model == _AUGMENTED:
            for name, entry in self.entries.items():
                if len(name) > len(source) and name[: len(source)] == source:
                    collected.add(entry)
            return collected
        for child in self.defined_strict_descendants(source):
            entry = self.entries.get(child)
            if entry is None:
                continue
            if model == _TRACKED and entry < self.era(child):
                continue
            collected.add(entry)
        return collected

    def comparison(self, candidates: set[int]) -> set[int]:
        survivors: set[int] = set()
        for candidate in candidates:
            excluded = False
            for newer in candidates:
                if newer > candidate and _operations_related(
                    self.operations[newer], self.operations[candidate]
                ):
                    excluded = True
                    break
            if not excluded:
                survivors.add(candidate)
        return survivors

    def reaches(self, source: int, target: int) -> bool:
        return bool(self.reachable[source] & (1 << target))

    def move_correction(self, survivors: set[int]) -> set[int]:
        if not self.apply_move_correction:
            return set(survivors)
        result: set[int] = set()
        for candidate in survivors:
            reached_move = False
            if self.operations[candidate].kind == _MOVE:
                for other in survivors:
                    if other != candidate and self.reaches(other, candidate):
                        reached_move = True
                        break
            if not reached_move:
                result.add(candidate)
        return result

    def dependencies_for(
        self,
        operation: _Operation,
        model: str,
        *,
        finished_empty_rule: bool = False,
    ) -> tuple[frozenset[int], set[int]]:
        """Return the final dependency set and the full candidate Collection.

        ``finished_empty_rule`` selects the Move Rule reading that combines the
        finished Empty Rule result instead of the raw Collection.
        """
        if operation.kind == _CREATE:
            fill = self.fill_candidate(operation.first)
            collection: set[int] = set()
            if fill is not None:
                collection.add(fill)
            return frozenset(collection), collection
        if operation.kind == _DESTROY:
            collection = self.empty_collection(operation.first, model)
            final = self.move_correction(self.comparison(collection))
            return frozenset(final), collection
        source_side = self.empty_collection(operation.first, model)
        fill = self.fill_candidate(operation.second)
        if finished_empty_rule:
            source_side = self.move_correction(self.comparison(source_side))
        collection = set(source_side)
        if fill is not None:
            collection.add(fill)
        final = self.move_correction(self.comparison(collection))
        if self.apply_fill_dependency_removal and fill is not None and fill in final:
            for remaining in final:
                if (
                    remaining != fill
                    and remaining in source_side
                    and self.reaches(remaining, fill)
                ):
                    final = final - {fill}
                    break
        return frozenset(final), collection

    def apply(
        self, operation: _Operation
    ) -> tuple[frozenset[int], _ModelResults, set[int], _UndoRecord]:
        """Apply the operation; return per-model results and an undo record."""
        tracked, collection = self.dependencies_for(operation, _TRACKED)
        specified, _ = self.dependencies_for(operation, _SPECIFIED)
        augmented, _ = self.dependencies_for(operation, _AUGMENTED)
        finished, _ = self.dependencies_for(
            operation, _TRACKED, finished_empty_rule=True
        )
        index = len(self.operations)
        undo_entries: _UndoValues = []
        undo_occupants: _UndoValues = []
        undo_arrival: _UndoValues = []

        def set_entry(key: tuple[str, ...], value: int):
            undo_entries.append((key, self.entries.get(key)))
            self.entries[key] = value

        def set_occupant(key: tuple[str, ...], value: int | None):
            undo_occupants.append((key, self.occupants.get(key)))
            if value is None:
                del self.occupants[key]
            else:
                self.occupants[key] = value

        def set_arrival(key: tuple[str, ...], value: int | None):
            undo_arrival.append((key, self.arrival.get(key)))
            if value is None:
                del self.arrival[key]
            else:
                self.arrival[key] = value

        self.operations.append(operation)
        self.dependencies.append(tracked)
        reach_mask = 0
        for dependency in tracked:
            reach_mask |= (1 << dependency) | self.reachable[dependency]
        self.reachable.append(reach_mask)

        if operation.kind == _CREATE:
            set_entry(operation.first, index)
            set_occupant(operation.first, self.created_kind(operation.first))
            set_arrival(operation.first, index)
        elif operation.kind == _DESTROY:
            set_entry(operation.first, index)
            set_occupant(operation.first, None)
            set_arrival(operation.first, None)
        else:
            descendants = self.defined_strict_descendants(operation.first)
            moved_relative_names = [
                name[len(operation.first) :] for name in descendants
            ]
            occupied_relative_names = [
                relative
                for relative in moved_relative_names
                if operation.first + relative in self.occupants
            ]
            set_entry(operation.first, index)
            set_entry(operation.second, index)
            for relative in moved_relative_names:
                set_entry(operation.second + relative, index)
            moved_kind = self.occupants[operation.first]
            moved_children: list[tuple[tuple[str, ...], int]] = []
            for relative in occupied_relative_names:
                moved_children.append(
                    (relative, self.occupants[operation.first + relative])
                )
            set_occupant(operation.first, None)
            set_arrival(operation.first, None)
            for relative, _ in moved_children:
                set_occupant(operation.first + relative, None)
                set_arrival(operation.first + relative, None)
            set_occupant(operation.second, moved_kind)
            set_arrival(operation.second, index)
            for relative, child_kind in moved_children:
                set_occupant(operation.second + relative, child_kind)
                set_arrival(operation.second + relative, index)

        undo_record = (undo_entries, undo_occupants, undo_arrival)
        return tracked, (specified, augmented, finished), collection, undo_record

    def undo(self, record: _UndoRecord):
        undo_entries, undo_occupants, undo_arrival = record
        _ = self.operations.pop()
        _ = self.dependencies.pop()
        _ = self.reachable.pop()
        for key, old_value in reversed(undo_entries):
            if old_value is None:
                del self.entries[key]
            else:
                self.entries[key] = old_value
        for key, old_value in reversed(undo_occupants):
            if old_value is None:
                _ = self.occupants.pop(key, None)
            else:
                self.occupants[key] = old_value
        for key, old_value in reversed(undo_arrival):
            if old_value is None:
                _ = self.arrival.pop(key, None)
            else:
                self.arrival[key] = old_value


@typing.final
class _MoveCorrectionDisabled(_RuleState):
    apply_move_correction: bool = False


@typing.final
class _FillDependencyRemovalDisabled(_RuleState):
    apply_move_correction: bool = False
    apply_fill_dependency_removal: bool = False


@typing.final
class _ViolationError(Exception):
    def __init__(self, kind: str, detail: str, sequence: list[_Operation]):
        super().__init__(detail)
        self.kind: str = kind
        self.detail: str = detail
        self.sequence: list[_Operation] = sequence


def _check_after_apply(
    state: _RuleState,
    tracked: frozenset[int],
    other_models: _ModelResults,
    collection: set[int],
) -> tuple[str, str] | None:
    index = len(state.operations) - 1
    operation = state.operations[index]
    specified, augmented, finished = other_models
    for model_name, model_dependencies in (
        ("specified", specified),
        ("augmented", augmented),
        ("finished_empty_rule", finished),
    ):
        if tracked != model_dependencies:
            return (
                "model_mismatch",
                (
                    f"operation {index} {operation}: tracked={sorted(tracked)} "
                    f"{model_name}={sorted(model_dependencies)}"
                ),
            )
    for one in tracked:
        if not _operations_related(operation, state.operations[one]):
            return (
                "edge_position_lemma",
                (
                    f"operation {index} {operation}: dependency {one} "
                    f"{state.operations[one]} operates on unrelated positions"
                ),
            )
        for other in tracked:
            if one != other and state.reaches(one, other):
                return (
                    "not_antichain",
                    (
                        f"operation {index} {operation}: dependency {one} "
                        f"{state.operations[one]} reaches dependency {other} "
                        f"{state.operations[other]}"
                    ),
                )
    reach_mask = state.reachable[index]
    for candidate in collection:
        if not reach_mask & (1 << candidate):
            return (
                "lost_candidate",
                (
                    f"operation {index} {operation}: Collection candidate "
                    f"{candidate} {state.operations[candidate]} is unreachable"
                ),
            )
    for earlier in range(index):
        if _operations_related(operation, state.operations[earlier]) and not (
            reach_mask & (1 << earlier)
        ):
            return (
                "statement_one",
                (
                    f"operation {index} {operation}: earlier related operation "
                    f"{earlier} {state.operations[earlier]} is unreachable"
                ),
            )
    return None


def _depth_first_search(
    state: _RuleState,
    depth_left: int,
    sequence: list[_Operation],
    budget: list[int],
):
    if budget[0] <= 0:
        return
    for operation in state.valid_operations():
        budget[0] -= 1
        if budget[0] <= 0:
            return
        tracked, other_models, collection, record = state.apply(operation)
        sequence.append(operation)
        problem = _check_after_apply(state, tracked, other_models, collection)
        if problem is not None:
            failing_sequence = list(sequence)
            _ = sequence.pop()
            state.undo(record)
            raise _ViolationError(problem[0], problem[1], failing_sequence)
        if depth_left > 1:
            _depth_first_search(state, depth_left - 1, sequence, budget)
        _ = sequence.pop()
        state.undo(record)


def _random_walks(config: _WorldConfig, trials: int, length: int, seed: int):
    generator = random.Random(seed)  # noqa: S311
    for _ in range(trials):
        state = _RuleState(config)
        sequence: list[_Operation] = []
        for _ in range(length):
            options = state.valid_operations()
            if not options:
                break
            weights: list[int] = []
            for option in options:
                if option.kind == _MOVE:
                    weights.append(4)
                elif option.kind == _CREATE:
                    weights.append(2)
                else:
                    weights.append(1)
            operation = generator.choices(options, weights)[0]
            tracked, other_models, collection, _ = state.apply(operation)
            sequence.append(operation)
            problem = _check_after_apply(state, tracked, other_models, collection)
            if problem is not None:
                raise _ViolationError(problem[0], problem[1], list(sequence))


def _find_violation(
    state_class: type[_RuleState], config: _WorldConfig, depth: int, budget: int
) -> _ViolationError | None:
    """Return the first violation a bounded search finds, or None."""
    try:
        _depth_first_search(state_class(config), depth, [], [budget])
    except _ViolationError as violation:
        return violation
    return None


def _self_test() -> bool:
    """Prove the checker detects the violations the corrections prevent."""
    correction_violation = _find_violation(
        _MoveCorrectionDisabled, _CONFIGS[1], depth=7, budget=2_000_000
    )
    if correction_violation is None:
        click.echo("SELF-TEST FAILED: no violation with the Move Correction disabled")
        return False
    if correction_violation.kind != "not_antichain":
        click.echo(f"SELF-TEST FAILED: unexpected kind {correction_violation.kind}")
        return False
    removal_violation = _find_violation(
        _FillDependencyRemovalDisabled, _CONFIGS[1], depth=7, budget=2_000_000
    )
    if removal_violation is None:
        click.echo(
            "SELF-TEST FAILED: no violation with the Fill Dependency removal disabled"
        )
        return False
    if removal_violation.kind != "not_antichain":
        click.echo(f"SELF-TEST FAILED: unexpected kind {removal_violation.kind}")
        return False
    click.echo("self-test: mutated rules produce the known violations as expected")
    return True


def _report(violation: _ViolationError):
    click.echo(f"== VIOLATION {violation.kind}")
    click.echo(f"   {violation.detail}")
    for index, operation in enumerate(violation.sequence):
        click.echo(f"   {index}: {operation}")


@click.command()
@click.option(
    "--depth",
    type=click.IntRange(min=1),
    default=6,
    help=(
        "Exhaustive search depth per world. The default of 6 finishes in "
        "seconds; 8 reproduces the full campaign and takes several minutes."
    ),
)
@click.option(
    "--budget",
    type=click.IntRange(min=1),
    default=1_000_000,
    help="Maximum operations explored per world in the exhaustive search.",
)
@click.option(
    "--trials",
    type=click.IntRange(min=0),
    default=5_000,
    help="Random walks per world.",
)
@click.option(
    "--length",
    type=click.IntRange(min=1),
    default=20,
    help="Operations per random walk.",
)
def main(depth: int, budget: int, trials: int, length: int):
    """Check the Particle Operation Dependency Graph rules by brute force.

    The run self-tests first, then explores every world shape exhaustively up
    to --depth operations (within --budget) and with --trials random walks of
    --length operations, verifying transitive reduction and the proof's
    invariants at every operation.
    """
    if not _self_test():
        sys.exit(1)

    start = time.time()
    for config in _CONFIGS:
        violation = _find_violation(_RuleState, config, depth, budget)
        if violation is not None:
            _report(violation)
            sys.exit(1)
        try:
            _random_walks(config, trials, length, seed=len(config.name))
        except _ViolationError as violation:
            _report(violation)
            sys.exit(1)
        click.echo(f"{config.name}: clean ({time.time() - start:.0f}s)")
    click.echo("OK: no violations found")


if __name__ == "__main__":
    main()
