"""Resolve Value Operations: work out what executing one runs, which depends on the encodings of the values it is executed on."""

from __future__ import annotations

import threading
import typing

import msgspec

from define.compiler import ast
from define.compiler.association_resolution import concrete_program
from define.compiler.validator.reference_graph import abstract_program

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from define.compiler.association_resolution import (
        associations as associations_module,
    )
    from define.compiler.association_resolution import literal_encoder
    from define.compiler.errors import diagnostics


class EncodedValueOperationExecution(msgspec.Struct):
    """An Operation Execution Statement in a Value Operation, with its literals encoded."""

    value_operation: ast.ValueOperationDefinition
    # The statement's name of the executed Value Operation, where diagnostics
    # about the execution are reported.
    operation: ast.GlobalTypedNameReference
    # In the order of the executed Value Operation's interface views.
    arguments: list[concrete_program.OperationArgument[ast.LocalTypedNameReference]]


# A step of a Value Operation, with its literals encoded.
type EncodedValueOperationStep = (
    ast.LocalViewDefinition
    | ast.ViewSettingStatement
    | abstract_program.LogicalOperationExecution
    | EncodedValueOperationExecution
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
type ResolvedValueOperation = (
    concrete_program.OperationExecution | MissingEncodingOperation | None
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
class ValueOperationResolver:
    """Works out what executing a Value Operation runs, once for each set of encodings it is executed on.

    Association resolution of all actions shares one, concurrently.
    """

    def __init__(
        self,
        associations: associations_module.Associations,
        encoder: literal_encoder.LiteralEncoder,
    ):
        """Initialize with the program's associations, the literal encoder, and no Value Operations."""
        self._associations = associations
        self._encoder = encoder
        # The steps of each Value Operation whose literals could be encoded,
        # by the Value Operation's full typed name.
        self._value_operation_steps: dict[str, list[EncodedValueOperationStep]] = {}
        # Each Value Operation's resolution for each set of encodings, with the
        # composite Value Operation it is, if it is one.
        self._resolutions: dict[
            _ValueOperationEncodings,
            tuple[
                ResolvedValueOperation, concrete_program.CompositeValueOperation | None
            ],
        ] = {}
        # The lock that one thread holds while it works out the resolution of
        # each key, so that each is worked out only once.
        self._resolution_locks: dict[_ValueOperationEncodings, threading.Lock] = {}

    def add_value_operation(
        self,
        definition: ast.ValueOperationDefinition,
        steps: Collection[abstract_program.ValueOperationStep],
    ) -> list[diagnostics.Diagnostic]:
        """Add a valid Value Operation, encoding the literals in its steps, and return the diagnostics about the ones that cannot be encoded."""
        enclosing_fqun = definition.typed_name.name_content.fqun
        encoded_steps: list[EncodedValueOperationStep] = []
        literal_diagnostics: list[diagnostics.Diagnostic] = []
        for step in steps:
            if not isinstance(step, abstract_program.ValueOperationExecution):
                encoded_steps.append(step)
                continue
            arguments, argument_diagnostics = self.resolve_arguments(
                step.arguments, enclosing_fqun
            )
            literal_diagnostics.extend(argument_diagnostics)
            if arguments is not None:
                encoded_steps.append(
                    EncodedValueOperationExecution(
                        value_operation=step.value_operation,
                        operation=step.operation,
                        arguments=arguments,
                    )
                )
        # A Value Operation with a literal that cannot be encoded has no steps,
        # so executing it runs nothing.
        if len(encoded_steps) == len(steps):
            self._value_operation_steps[definition.typed_name.full_typed_name] = (
                encoded_steps
            )
        return literal_diagnostics

    def resolve_arguments[LookedAtT](
        self,
        arguments: Iterable[
            abstract_program.Argument[
                ast.InterfaceViewDefinition, LookedAtT | ast.Literal
            ]
        ],
        enclosing_fqun: ast.Fqun,
    ) -> tuple[
        list[concrete_program.OperationArgument[LookedAtT]] | None,
        list[diagnostics.Diagnostic],
    ]:
        """Return the arguments of an execution of a Value Operation with each literal in the encoding of the value quality of the view that looks at it, if every literal can be encoded, and the diagnostics explaining why not.

        enclosing_fqun is the FQUN of the definition that contains the
        execution, from whose universe the diagnostics name things.
        """
        encoded: list[concrete_program.OperationArgument[LookedAtT]] = []
        literal_diagnostics: list[diagnostics.Diagnostic] = []
        for argument in arguments:
            looking_at = argument.looking_at
            if not isinstance(looking_at, ast.Literal):
                encoded.append(
                    concrete_program.OperationArgument(
                        interface_view=argument.interface_view, looking_at=looking_at
                    )
                )
                continue
            value_quality = (
                argument.interface_view.quality_assignment_block.value_quality
            )
            # Structural validation reports a view without a value quality.
            if value_quality is None:
                return None, literal_diagnostics
            value_encoding = self._associations.value_encoding(value_quality)
            # A missing value quality, or one without an encoding, was already
            # reported.
            if value_encoding is None:
                return None, literal_diagnostics
            value, encoding_diagnostics = self._encoder.encode(
                looking_at, value_quality, value_encoding, enclosing_fqun
            )
            literal_diagnostics.extend(encoding_diagnostics)
            if value is None:
                return None, literal_diagnostics
            encoded.append(
                concrete_program.OperationArgument(
                    interface_view=argument.interface_view, looking_at=value
                )
            )
        return encoded, literal_diagnostics

    def composite_value_operations(
        self,
    ) -> dict[str, list[concrete_program.CompositeValueOperation]]:
        """Return every composite Value Operation worked out, grouped by its Value Operation's full typed name and sorted by its encodings."""
        by_value_operation: dict[
            str, list[concrete_program.CompositeValueOperation]
        ] = {}
        for _, composite in self._resolutions.values():
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

    def resolve(
        self,
        value_operation: ast.ValueOperationDefinition,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> ResolvedValueOperation:
        """Return what executing the Value Operation runs when its interface views have ``view_encodings``, keyed by each view's source typed name."""
        encodings: list[ast.GlobalTypedNameReference] = []
        for view in value_operation.views:
            encodings.append(view_encodings[view.typed_name.source_typed_name])
        key = (
            value_operation.typed_name.full_typed_name,
            _full_typed_names(encodings),
        )
        result, _ = self._resolve_once(key, value_operation, view_encodings)
        return result

    def _resolve_once(
        self,
        key: _ValueOperationEncodings,
        value_operation: ast.ValueOperationDefinition,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> tuple[ResolvedValueOperation, concrete_program.CompositeValueOperation | None]:
        """Return the resolution of the Value Operation for the encodings that key names, working it out only if no thread has."""
        resolution = self._resolutions.get(key)
        if resolution is not None:
            return resolution
        # CPython's dict.setdefault is atomic, with or without the GIL, so
        # every thread that needs this key gets the same lock.
        # A thread waits only for the lock of a Value Operation that the one it
        # is working out executes, directly or through others. Value
        # Operations cannot execute each other in a cycle, so two threads never
        # wait for each other.
        with self._resolution_locks.setdefault(key, threading.Lock()):
            resolution = self._resolutions.get(key)
            if resolution is None:
                resolution = self._resolve_uncached_value_operation(
                    value_operation, view_encodings
                )
                self._resolutions[key] = resolution
        return resolution

    def _resolve_uncached_value_operation(
        self,
        value_operation: ast.ValueOperationDefinition,
        interface_view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> tuple[ResolvedValueOperation, concrete_program.CompositeValueOperation | None]:
        """Work out what executing the Value Operation runs when its interface views have ``interface_view_encodings``, and return it with the composite Value Operation it is, if it is one."""
        steps = self._value_operation_steps.get(
            value_operation.typed_name.full_typed_name
        )
        # A Value Operation with diagnostics has no steps.
        if steps is None:
            return None, None
        # Local views are added as they are defined.
        view_encodings = dict(interface_view_encodings)
        composite_steps: list[concrete_program.OperationStep] = []
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
                case abstract_program.LogicalOperationExecution():
                    execution = self._encoding_operation_execution(step, view_encodings)
                    if isinstance(execution, MissingEncodingOperation):
                        return execution, None
                    composite_steps.append(execution)
                case EncodedValueOperationExecution():
                    execution = self._value_operation_execution(step, view_encodings)
                    if not isinstance(execution, concrete_program.OperationExecution):
                        return execution, None
                    composite_steps.append(execution)
        # Calling a function that makes a single execution is no smaller than
        # making that execution where the Value Operation is executed.
        if len(composite_steps) == 1:
            # Structural validation reports a Value Operation that executes
            # nothing, so its only step is an execution.
            only_step = typing.cast(
                "concrete_program.OperationExecution", composite_steps[0]
            )
            return only_step, None
        arguments: list[
            concrete_program.OperationArgument[ast.LocalTypedNameReference]
        ] = []
        for view in value_operation.views:
            arguments.append(
                concrete_program.OperationArgument(
                    interface_view=view, looking_at=view.typed_name
                )
            )
        composite = concrete_program.CompositeValueOperation(
            definition=value_operation,
            view_encodings=interface_view_encodings,
            steps=composite_steps,
        )
        return concrete_program.OperationExecution(
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
        return self._associations.value_encoding(value_quality)

    def _encoding_operation_execution(
        self,
        execution: abstract_program.LogicalOperationExecution,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> concrete_program.OperationExecution | MissingEncodingOperation:
        """Return the execution of the Encoding Operation that performs a logical operation for the encodings of the views it looks at."""
        encodings: list[ast.GlobalTypedNameReference] = []
        for argument in execution.arguments:
            encodings.append(view_encodings[argument.looking_at.source_typed_name])
        encoding_operation = self._associations.encoding_operation(
            execution.logical_operation, _full_typed_names(encodings)
        )
        if encoding_operation is None:
            missing_view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
            for argument in execution.arguments:
                missing_view_encodings[
                    argument.interface_view.typed_name.source_typed_name
                ] = view_encodings[argument.looking_at.source_typed_name]
            return MissingEncodingOperation(
                view_encodings=missing_view_encodings,
                execution_stack=(execution.logical_operation,),
            )
        arguments: list[
            concrete_program.OperationArgument[ast.LocalTypedNameReference]
        ] = []
        for argument in execution.arguments:
            arguments.append(
                concrete_program.OperationArgument(
                    interface_view=argument.interface_view,
                    looking_at=argument.looking_at,
                )
            )
        return concrete_program.OperationExecution(
            runtime_operation=encoding_operation, arguments=arguments
        )

    def _value_operation_execution(
        self,
        execution: EncodedValueOperationExecution,
        view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> concrete_program.OperationExecution | MissingEncodingOperation | None:
        """Return what an execution of another Value Operation runs, for the encodings of what its arguments look at."""
        executed_view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for argument in execution.arguments:
            looking_at = argument.looking_at
            executed_view = argument.interface_view.typed_name.source_typed_name
            if isinstance(looking_at, concrete_program.EncodedLiteral):
                executed_view_encodings[executed_view] = looking_at.encoding
            else:
                executed_view_encodings[executed_view] = view_encodings[
                    looking_at.source_typed_name
                ]
        executed = self.resolve(execution.value_operation, executed_view_encodings)
        if isinstance(executed, MissingEncodingOperation):
            return MissingEncodingOperation(
                view_encodings=executed.view_encodings,
                execution_stack=(execution.operation, *executed.execution_stack),
            )
        if executed is None:
            return None
        return concrete_program.OperationExecution(
            runtime_operation=executed.runtime_operation,
            arguments=executed.arguments_for(execution.arguments),
        )
