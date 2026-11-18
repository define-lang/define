"""Runs each stage of each definition as soon as what it depends on is done."""

from __future__ import annotations

import collections
import enum
import functools
import typing

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    abstract_program,
    reference_graph_validator,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler import work_pool
    from define.compiler.association_resolution import association_resolver
    from define.compiler.errors import diagnostics
    from define.compiler.graphs import reference_graph_order


class Stage(enum.IntEnum):
    """A stage that every definition passes through, in order."""

    VALIDATE = 0
    RESOLVE = 1


_STAGES = tuple(Stage)


@typing.final
class DefinitionPipeline:
    """Runs each stage of each definition in a pool, once the definition has finished its previous stage and everything it directly references has finished this one.

    Every definition goes through every stage, even a stage that has nothing to
    do for it. A definition can't finish a stage until every definition it
    references has finished that stage. A definition that the stage skips must
    also wait for every definition it references, because a definition can
    depend on another definition indirectly, through a skipped definition.

    Only the pool's coordinator thread may use the pipeline.
    """

    def __init__(
        self,
        order: reference_graph_order.ReferenceGraphOrder,
        validator: reference_graph_validator.ReferenceGraphValidator,
        resolver: association_resolver.AssociationResolver,
        pool: work_pool.WorkPool,
    ):
        """Initialize with the order, the stages' work, and the pool to run it in."""
        self._order = order
        self._validator = validator
        self._resolver = resolver
        self._pool = pool
        # For each stage, indexed by the stage, how many of each definition's
        # direct references have not finished that stage.
        self._remaining = [order.new_reference_counts() for _ in _STAGES]
        # How many stages each definition has finished.
        self._finished_stages = bytearray(len(order.definitions))
        # The abstract definition that validation produced for each definition,
        # by the definition's index in the order. A definition's entry is
        # removed when its resolution starts.
        self._abstract_definitions: dict[
            int, abstract_program.AbstractDefinition | None
        ] = {}
        self._diagnostics: list[diagnostics.Diagnostic] = []

    def run(self) -> list[diagnostics.Diagnostic]:
        """Run every stage of every definition, and return the diagnostics they reported."""
        self._advance(
            (index, Stage.VALIDATE) for index in self._order.leaf_definition_indexes()
        )
        self._pool.run_until_idle()
        return self._diagnostics

    def _advance(self, ready: Iterable[tuple[int, Stage]]):
        """Start each ready stage, finishing at once the ones with nothing to run on a worker, which can make more ready."""
        # A worklist rather than recursion, since finishing one stage at once
        # can make a long chain of others ready.
        pending = collections.deque(ready)
        while pending:
            index, stage = pending.popleft()
            if self._start(index, stage):
                pending.extend(self._finish(index, stage))

    def _start(self, index: int, stage: Stage) -> bool:
        """Start a stage for a definition, and return whether the stage is already done, because the stage had nothing to do for the definition or ran on the coordinator thread instead of a worker."""
        definition = self._order.definitions[index]
        match stage:
            case Stage.VALIDATE:
                if not reference_graph_validator.requires_validation(definition):
                    return True
                self._pool.submit(
                    self._validator.validate_definition,
                    definition,
                    handle_result=functools.partial(self._handle_validation, index),
                )
                return False
            case Stage.RESOLVE:
                abstract = self._abstract_definitions.pop(index, None)
                # A Value Operation whose steps validation could not work out,
                # and every kind that validation skips, have nothing to
                # resolve.
                if abstract is None:
                    return True
                handle_result = functools.partial(self._handle_resolution, index)
                match abstract:
                    case abstract_program.AbstractAction():
                        self._pool.submit(
                            self._resolver.resolve_action,
                            abstract,
                            handle_result=handle_result,
                        )
                        return False
                    case abstract_program.AbstractValueOperation():
                        self._pool.submit(
                            self._resolver.resolve_value_operation,
                            abstract,
                            handle_result=handle_result,
                        )
                        return False
                    # Resolving a logical operation or a value quality is a
                    # lookup in its project's associations, which costs less
                    # than handing the lookup to a worker.
                    case ast.LogicalOperationDefinition():
                        self._diagnostics.extend(
                            self._resolver.resolve_logical_operation(abstract)
                        )
                        return True
                    case ast.ValueDefinition():
                        self._diagnostics.extend(self._resolver.resolve_value(abstract))
                        return True

    def _handle_validation(
        self,
        index: int,
        validation: reference_graph_validator.DefinitionValidation,
        _pool: work_pool.WorkPool,
    ):
        self._diagnostics.extend(validation.diagnostics)
        self._abstract_definitions[index] = validation.abstract
        self._advance(self._finish(index, Stage.VALIDATE))

    def _handle_resolution(
        self,
        index: int,
        resolution_diagnostics: list[diagnostics.Diagnostic],
        _pool: work_pool.WorkPool,
    ):
        self._diagnostics.extend(resolution_diagnostics)
        self._advance(self._finish(index, Stage.RESOLVE))

    def _finish(self, index: int, stage: Stage) -> list[tuple[int, Stage]]:
        """Record that a definition finished a stage, and return the stages that became ready."""
        self._finished_stages[index] = stage + 1
        ready: list[tuple[int, Stage]] = []
        remaining = self._remaining[stage]
        for dependent_index in self._order.dependent_definition_indexes(index):
            remaining[dependent_index] -= 1
            if (
                remaining[dependent_index] == 0
                and self._finished_stages[dependent_index] == stage
            ):
                ready.append((dependent_index, stage))
        if stage + 1 < len(_STAGES):
            next_stage = _STAGES[stage + 1]
            if self._remaining[next_stage][index] == 0:
                ready.append((index, next_stage))
        return ready
