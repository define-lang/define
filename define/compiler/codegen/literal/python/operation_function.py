"""Literal Python generation for the function of an Encoding Operation or of a composite Value Operation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.codegen.literal.python import naming, renderer, value_types
from define.compiler.validator import codegen_input

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class FunctionLocals(msgspec.Struct, frozen=True):
    """The local names of one generated function, and the modules it imports."""

    names: naming.LocalNameAllocator
    # Keyed by each view's source typed name.
    view_names: dict[str, str]
    imports: set[str]


def name_function_locals(
    function: renderer.FunctionReference,
    views: Sequence[ast.InterfaceViewDefinition],
    callees: Sequence[renderer.FunctionReference],
) -> FunctionLocals:
    """Name the local of each of a function's interface views, without hiding any module it imports or any function in its module that it calls."""
    imports = {
        callee.module_name
        for callee in callees
        if callee.module_name != function.module_name
    }
    names = naming.LocalNameAllocator()
    # A view's local name must not hide an imported module, or a function in
    # this module that the function calls.
    names.reserve_module_first_names(imports)
    names.reserve_module_first_names(
        callee.function_name
        for callee in callees
        if callee.module_name == function.module_name
    )
    view_names: dict[str, str] = {}
    for view in views:
        view_names[view.typed_name.source_typed_name] = names.allocate(
            naming.VIEW_PREFIX + view.typed_name.name_content.name
        )
    return FunctionLocals(names=names, view_names=view_names, imports=imports)


def generate_step_function(
    converter: naming.NameConverter,
    function: renderer.FunctionReference,
    views: Sequence[ast.InterfaceViewDefinition],
    view_python_types: Sequence[str],
    steps: Sequence[codegen_input.OperationStep],
) -> renderer.OperationFunction:
    """Build the template context for a function with the interface views ``views``, whose values have the Python types ``view_python_types``, that performs ``steps``."""
    callees: list[renderer.FunctionReference] = []
    for step in steps:
        if isinstance(step, codegen_input.OperationExecution):
            callees.append(
                converter.runtime_operation_function_reference(step.runtime_operation)
            )
    function_locals = name_function_locals(function, views, callees)
    statements, last_written_names = _step_statements(converter, steps, function_locals)
    return finish_function(
        function,
        views,
        view_python_types,
        function_locals,
        statements,
        last_written_names,
    )


def finish_function(
    function: renderer.FunctionReference,
    views: Sequence[ast.InterfaceViewDefinition],
    view_python_types: Sequence[str],
    function_locals: FunctionLocals,
    statements: list[renderer.OperationStatement],
    last_written_names: list[str],
) -> renderer.OperationFunction:
    """Build the template context for a function with the interface views ``views``, whose values have the Python types ``view_python_types``, from its statements and the local names that the last of them assigns, in order."""
    parameters: list[renderer.TypedLocalName] = []
    results: list[renderer.TypedLocalName] = []
    for view, python_type in zip(views, view_python_types, strict=True):
        view_local = renderer.TypedLocalName(
            name=function_locals.view_names[view.typed_name.source_typed_name],
            python_type=python_type,
        )
        if view.is_input:
            parameters.append(view_local)
        if view.is_output:
            results.append(view_local)
    result_names = [result.name for result in results]
    return renderer.OperationFunction(
        function_name=function.function_name,
        module_name=function.module_name,
        parameters=parameters,
        statements=statements,
        results=results,
        # Returning the last statement's expression avoids assigning locals
        # only to return them.
        return_last_statement=bool(results) and last_written_names == result_names,
        imports=function_locals.imports,
    )


def _step_statements(
    converter: naming.NameConverter,
    steps: Sequence[codegen_input.OperationStep],
    function_locals: FunctionLocals,
) -> tuple[list[renderer.OperationStatement], list[str]]:
    """Return the statements that perform ``steps``, and the local names that the last of them assigns, in order, naming each local view in the function's locals."""
    names = function_locals.names
    view_names = function_locals.view_names
    statements: list[renderer.OperationStatement] = []
    last_written_names: list[str] = []
    for step in steps:
        match step:
            case ast.LocalViewDefinition():
                view_names[step.typed_name.source_typed_name] = names.allocate(
                    naming.VIEW_PREFIX + step.typed_name.name_content.name
                )
            case codegen_input.OperationExecution():
                call = _call(
                    converter.runtime_operation_function_reference(
                        step.runtime_operation
                    ),
                    step.arguments,
                    view_names,
                )
                statements.append(call)
                last_written_names = call.results
            case ast.ViewSettingStatement():
                target = view_names[step.target.source_typed_name]
                statements.append(
                    renderer.OperationStatement.Assignment(
                        target=target,
                        source=view_names[step.source.source_typed_name],
                    )
                )
                last_written_names = [target]
    return statements, last_written_names


def _call(
    function: renderer.FunctionReference,
    execution_arguments: Sequence[
        codegen_input.OperationArgument[ast.LocalTypedNameReference]
    ],
    view_names: Mapping[str, str],
) -> renderer.OperationStatement.Call:
    arguments: list[str] = []
    results: list[str] = []
    for argument in execution_arguments:
        looking_at = argument.looking_at
        if isinstance(looking_at, codegen_input.EncodedLiteral):
            looked_at = value_types.python_literal(looking_at)
        else:
            looked_at = view_names[looking_at.source_typed_name]
        if argument.interface_view.is_input:
            arguments.append(looked_at)
        if argument.interface_view.is_output:
            results.append(looked_at)
    return renderer.OperationStatement.Call(
        function=function, arguments=arguments, results=results
    )
