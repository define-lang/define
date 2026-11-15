"""Work out what executing a Value Operation runs, which depends on the encodings of the values it is executed on."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.validator import codegen_input, validation_result

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )


class MissingEncodingOperation(msgspec.Struct, frozen=True):
    """Why an execution of a Value Operation cannot run: a logical operation it executes has no Encoding Operation for the encodings it is given."""

    # The encoding of each of the logical operation's views, keyed by the
    # view's source typed name, in the order of its views.
    view_encodings: dict[str, ast.GlobalTypedNameReference]
    # The name of the executed operation in each execution, from the first
    # one in the Value Operation that an action executes down to the Logical
    # Operation Execution Statement, in the order they happen. Each execution
    # is in the operation that the one before it executes.
    execution_stack: tuple[ast.GlobalTypedNameReference, ...]

    @property
    def logical_operation(self) -> ast.GlobalTypedNameReference:
        """The logical operation that no Encoding Operation performs."""
        return self.execution_stack[-1]


# What executing a Value Operation runs, as an execution whose arguments look
# at the Value Operation's own interface views. None means it cannot run for a
# reason that is already reported.
type ValueOperationExecutionResult = (
    codegen_input.OperationExecution | MissingEncodingOperation | None
)

# A Value Operation and the encodings of its interface views, in their order,
# by their full typed names, because typed names also compare their source
# locations.
type _ValueOperationEncodings = tuple[str, tuple[str, ...]]


def _full_typed_names(
    encodings: Iterable[ast.GlobalTypedNameReference],
) -> tuple[str, ...]:
    return tuple(encoding.full_typed_name for encoding in encodings)


@typing.final
class ValueOperationExecutions:
    """Works out what executing a Value Operation runs, once for each set of encodings it is executed on.

    The validators of all actions share one, concurrently.
    """

    def __init__(
        self,
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Initialize with the state that holds each Value Operation's steps and each logical operation's Encoding Operations."""
        self._validation_state = validation_state
        self._results: dict[
            _ValueOperationEncodings,
            tuple[
                ValueOperationExecutionResult,
                codegen_input.CompositeValueOperation | None,
            ],
        ] = {}

    def composite_value_operations(
        self,
    ) -> dict[str, list[codegen_input.CompositeValueOperation]]:
        """Return every composite Value Operation worked out, grouped by its Value Operation's full typed name and sorted by its encodings."""
        by_value_operation: dict[str, list[codegen_input.CompositeValueOperation]] = {}
        for _, composite in self._results.values():
            if composite is not None:
                by_value_operation.setdefault(
                    composite.definition.typed_name.full_typed_name, []
                ).append(composite)
        # Value Operations are validated concurrently, so they are ordered by
        # their encodings, which does not depend on that.
        for composite_list in by_value_operation.values():
            composite_list.sort(
                key=lambda composite: _full_typed_names(composite.encodings())
            )
        return by_value_operation

    def choose_encoding_operations(
        self,
        value_operation: ast.ValueOperationDefinition,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> ValueOperationExecutionResult:
        """Return what executing the Value Operation runs when its interface views have ``view_encodings``, keyed by each view's source typed name."""
        encodings: list[ast.GlobalTypedNameReference] = []
        for view in value_operation.views:
            encodings.append(view_encodings[view.typed_name.source_typed_name])
        key = (
            value_operation.typed_name.full_typed_name,
            _full_typed_names(encodings),
        )
        if key not in self._results:
            # Both supported Python runtimes make setdefault atomic.
            # Concurrent duplicate choices are harmless, and every caller
            # receives the result selected for the memo.
            _ = self._results.setdefault(
                key,
                self._choose_uncached_encoding_operations(
                    value_operation, view_encodings
                ),
            )
        result, _ = self._results[key]
        return result

    def _choose_uncached_encoding_operations(
        self,
        value_operation: ast.ValueOperationDefinition,
        interface_view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> tuple[
        ValueOperationExecutionResult, codegen_input.CompositeValueOperation | None
    ]:
        """Work out what executing the Value Operation runs when its interface views have ``interface_view_encodings``, and return it with the composite Value Operation it is, if it is one."""
        steps = self._validation_state.get_value_operation_steps(
            value_operation.typed_name
        )
        # A Value Operation with diagnostics publishes no steps.
        if steps is None:
            return None, None
        # Local views are added as they are defined.
        view_encodings = dict(interface_view_encodings)
        composite_steps: list[codegen_input.OperationStep] = []
        for step in steps:
            match step:
                case ast.LocalViewDefinition():
                    encoding = self._local_view_encoding(step)
                    # A missing value quality, or one without an encoding,
                    # was already reported.
                    if encoding is None:
                        return None, None
                    view_encodings[step.typed_name.source_typed_name] = encoding
                    composite_steps.append(step)
                case ast.ViewSettingStatement():
                    composite_steps.append(step)
                case validation_result.LogicalOperationExecution():
                    execution = self._encoding_operation_execution(step, view_encodings)
                    if isinstance(execution, MissingEncodingOperation):
                        return execution, None
                    composite_steps.append(execution)
                case validation_result.ValueOperationExecution():
                    execution = self._value_operation_execution(step, view_encodings)
                    if not isinstance(execution, codegen_input.OperationExecution):
                        return execution, None
                    composite_steps.append(execution)
                case ast.EncodingOperationExecutionStatement():
                    # TODO: Remove this once `execute the encoding operation.`
                    # is deleted. Nothing performs it any more.
                    return None, None
        # Calling a function that makes a single execution is no smaller than
        # making that execution where the Value Operation is executed.
        if len(composite_steps) == 1:
            # Structural validation reports a Value Operation that executes
            # nothing, so its only step is an execution.
            only_step = typing.cast(
                "codegen_input.OperationExecution", composite_steps[0]
            )
            return only_step, None
        arguments: list[
            codegen_input.OperationArgument[ast.LocalTypedNameReference]
        ] = []
        for view in value_operation.views:
            arguments.append(
                codegen_input.OperationArgument(
                    interface_view=view, looking_at=view.typed_name
                )
            )
        composite = codegen_input.CompositeValueOperation(
            definition=value_operation,
            view_encodings=interface_view_encodings,
            steps=composite_steps,
        )
        return codegen_input.OperationExecution(
            runtime_operation=composite, arguments=arguments
        ), composite

    def _local_view_encoding(
        self, view: ast.LocalViewDefinition
    ) -> ast.GlobalTypedNameReference | None:
        # TODO: Once a value quality can have more than one encoding, give a
        # local view the encoding of what the Encoding Operation that writes
        # it writes, which means choosing Encoding Operations by the encodings
        # of the views they read.
        value_quality = view.quality_assignment_block.value_quality
        # Structural validation reports a local view without a value quality.
        if value_quality is None:
            return None
        return self._validation_state.get_value_encoding(value_quality)

    def _encoding_operation_execution(
        self,
        execution: validation_result.LogicalOperationExecution,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> codegen_input.OperationExecution | MissingEncodingOperation:
        """Return the execution of the Encoding Operation that performs a logical operation for the encodings of the views it looks at."""
        encodings: list[ast.GlobalTypedNameReference] = []
        for argument in execution.arguments:
            encodings.append(view_encodings[argument.looking_at.source_typed_name])
        encoding_operation = self._validation_state.get_encoding_operations(
            execution.logical_operation
        ).get(_full_typed_names(encodings))
        if encoding_operation is None:
            missing_view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
            for argument in execution.arguments:
                missing_view_encodings[argument.view.source_typed_name] = (
                    view_encodings[argument.looking_at.source_typed_name]
                )
            return MissingEncodingOperation(
                view_encodings=missing_view_encodings,
                execution_stack=(execution.logical_operation,),
            )
        arguments: list[
            codegen_input.OperationArgument[ast.LocalTypedNameReference]
        ] = []
        # ZIP: The index holds only Encoding Operations whose views have the
        # names and order of the logical operation's views, and the statement's
        # arguments are in the logical operation's view order. So each argument
        # is for the Encoding Operation's view at its position.
        for interface_view, argument in zip(
            encoding_operation.views, execution.arguments, strict=True
        ):
            arguments.append(
                codegen_input.OperationArgument(
                    interface_view=interface_view, looking_at=argument.looking_at
                )
            )
        return codegen_input.OperationExecution(
            runtime_operation=encoding_operation.typed_name, arguments=arguments
        )

    def _value_operation_execution(
        self,
        execution: validation_result.ValueOperationExecution,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> codegen_input.OperationExecution | MissingEncodingOperation | None:
        """Return what an execution of another Value Operation runs, for the encodings of what its arguments look at."""
        executed_view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for argument in execution.arguments:
            looking_at = argument.looking_at
            executed_view = argument.interface_view.typed_name.source_typed_name
            if isinstance(looking_at, codegen_input.EncodedLiteral):
                executed_view_encodings[executed_view] = looking_at.encoding
            else:
                executed_view_encodings[executed_view] = view_encodings[
                    looking_at.source_typed_name
                ]
        executed = self.choose_encoding_operations(
            execution.value_operation, executed_view_encodings
        )
        if isinstance(executed, MissingEncodingOperation):
            return MissingEncodingOperation(
                view_encodings=executed.view_encodings,
                execution_stack=(execution.operation, *executed.execution_stack),
            )
        if executed is None:
            return None
        return codegen_input.OperationExecution(
            runtime_operation=executed.runtime_operation,
            arguments=executed.arguments_for(execution.arguments),
        )
