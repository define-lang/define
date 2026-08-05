"""Validation of the reference graph."""

from __future__ import annotations

import threading
import typing
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.graphs import action_call_graph, reference_graph
from define.compiler.validator.reference_graph import (
    definition_postorder_validator,
    operation_graph,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    import collections.abc

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result

# Position definitions get no validation and so produce None.
type _PostorderResult = definition_postorder_validator.PostorderValidationResult | None


class _ReferencedDefinitionValidationError(Exception):
    """A definition could not be validated because a reference failed."""


class _PendingDefinitionValidation:
    """Starts one definition after its referenced definitions complete."""

    _completion: Future[_PostorderResult]
    _definition: ast.QualityDefinition
    _remaining_references: int | None
    _scheduling_lock: threading.Lock
    _start_definition: collections.abc.Callable[
        [ast.QualityDefinition, Future[_PostorderResult]], None
    ]

    def __init__(
        self,
        definition: ast.QualityDefinition,
        reference_count: int,
        start_definition: collections.abc.Callable[
            [ast.QualityDefinition, Future[_PostorderResult]], None
        ],
    ):
        self._completion = Future()
        self._definition = definition
        self._remaining_references = reference_count
        self._scheduling_lock = threading.Lock()
        self._start_definition = start_definition

    def start_when_references_complete(
        self,
        referenced_futures: list[Future[_PostorderResult]],
    ):
        """Register referenced definitions and start when they are ready."""
        if not referenced_futures:
            self._start_definition(self._definition, self._completion)
            return
        for referenced_future in referenced_futures:
            referenced_future.add_done_callback(self._reference_completed)

    @property
    def future(self) -> Future[_PostorderResult]:
        return self._completion

    def result(self) -> _PostorderResult:
        return self._completion.result()

    def _reference_completed(
        self,
        referenced_future: Future[_PostorderResult],
    ):
        reference_completed_successfully = referenced_future.exception() is None
        start_definition = False
        with self._scheduling_lock:
            if self._remaining_references is None:
                return
            if not reference_completed_successfully:
                self._remaining_references = None
            else:
                self._remaining_references -= 1
                if self._remaining_references == 0:
                    self._remaining_references = None
                    start_definition = True

        if not reference_completed_successfully:
            # This completion future was not submitted to an executor, so
            # cancel() would never reach the CANCELLED_AND_NOTIFIED state that
            # concurrent.futures.wait() requires before it stops waiting. Thus
            # we use this sentinel exception to indicate completion in the error
            # case, instead of cancel().
            self._completion.set_exception(_ReferencedDefinitionValidationError())
        elif start_definition:
            self._start_definition(self._definition, self._completion)


class _ValidatorWorkPool:
    """Runs definition validation after referenced definitions complete."""

    _executor: ThreadPoolExecutor
    _validation_by_name: dict[str, _PendingDefinitionValidation]
    _validate_action: collections.abc.Callable[
        [ast.ActionDefinition],
        definition_postorder_validator.PostorderValidationResult,
    ]

    def __init__(
        self,
        validate_action: collections.abc.Callable[
            [ast.ActionDefinition],
            definition_postorder_validator.PostorderValidationResult,
        ],
        max_workers: int | None = None,
    ):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._validation_by_name = {}
        self._validate_action = validate_action

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True)

    def submit(
        self,
        definition: ast.QualityDefinition,
        referenced_definitions: collections.abc.Iterable[ast.QualityDefinition],
    ):
        """Submit a definition to start after its references are ready."""
        referenced_futures = [
            self._validation_by_name[
                referenced_definition.typed_name.full_typed_name
            ].future
            for referenced_definition in referenced_definitions
        ]
        validation = _PendingDefinitionValidation(
            definition,
            len(referenced_futures),
            self._start_definition,
        )
        self._validation_by_name[definition.typed_name.full_typed_name] = validation
        validation.start_when_references_complete(referenced_futures)

    def wait(self):
        """Wait for every submitted definition to complete."""
        _ = wait(validation.future for validation in self._validation_by_name.values())

    def result(self, definition: ast.QualityDefinition) -> _PostorderResult:
        """Return the completed validation result for ``definition``."""
        return self._validation_by_name[definition.typed_name.full_typed_name].result()

    def _start_definition(
        self,
        definition: ast.QualityDefinition,
        validator_future: Future[_PostorderResult],
    ):
        if not isinstance(definition, ast.ActionDefinition):
            validator_future.set_result(None)
            return

        executor_future = self._executor.submit(self._validate_action, definition)
        executor_future.add_done_callback(
            lambda completed_executor_future: self._complete_future(
                completed_executor_future, validator_future
            )
        )

    def _complete_future(
        self,
        executor_future: Future[
            definition_postorder_validator.PostorderValidationResult
        ],
        validator_future: Future[_PostorderResult],
    ):
        exception = executor_future.exception()
        if exception is not None:
            validator_future.set_exception(exception)
        else:
            validator_future.set_result(executor_future.result())


@dataclass(frozen=True, slots=True)
class ReferenceGraphValidationResult:
    """What reference graph validation produces, beyond the diagnostics it reports."""

    action_call_graph: action_call_graph.ActionCallGraph
    # The DLP 44 operation dependency graph of every action.
    operation_graphs: operation_graph.OperationGraphs


# TODO: We need a mode that forces a fake caller as the parent of any top-level
# action in this graph, to make sure that caller requirements are detected.
# (Otherwise developers can write bad action code and not realize it.)
class ReferenceGraphValidator:
    """Verifies all definitions using the reference graph.

    This is the primary logical validator of Define. After completing structural
    validation, this step walks through the reference graph in DFS post-order
    and performs validations on each definition for logical correctness.
    """

    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState

    def __init__(
        self,
        graph: reference_graph.ReferenceGraph,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
    ):
        """Initialize with the reference graph and definition results."""
        self._reference_graph = graph
        self._definition_results = definition_results
        self._validation_state = (
            reference_graph_validation_state.ReferenceGraphValidationState()
        )

    def validate(
        self, max_workers: int | None = None
    ) -> ReferenceGraphValidationResult:
        """Run analysis for all definitions in a depth-first-search, post-order."""
        definitions = list(self._reference_graph.dfs_postorder_all())
        with _ValidatorWorkPool(self._validate_action, max_workers=max_workers) as pool:
            for definition in definitions:
                pool.submit(
                    definition,
                    self._reference_graph.referenced_definitions(definition),
                )
            pool.wait()

        call_graph = action_call_graph.ActionCallGraph()
        operation_graphs = operation_graph.OperationGraphs()
        for definition in definitions:
            result = pool.result(definition)
            if result is None:
                continue
            definition_result = self._definition_results[definition.typed_name]
            for d in result.diagnostics:
                definition_result.add_diagnostic(d)
            for edge in result.edges:
                call_graph.add_edge(edge.source, edge.target)
            operation_graphs[definition.typed_name] = result.operation_graph
        return ReferenceGraphValidationResult(
            action_call_graph=call_graph,
            operation_graphs=operation_graphs,
        )

    def _validate_action(
        self, definition: ast.ActionDefinition
    ) -> definition_postorder_validator.PostorderValidationResult:
        definition_result = self._definition_results[definition.typed_name]
        result = definition_postorder_validator.ActionPostorderValidator(
            definition_result,
            self._definition_results,
            self._validation_state,
        ).analyze()
        self._validation_state.publish_contract(definition.typed_name, result.contract)
        return result
