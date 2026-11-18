"""The compiler's validation stages, from a structurally validated program to its concrete program, without code generation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.association_resolution import (
    association_resolver,
    association_tables,
)
from define.compiler.graphs import reference_graph_executor
from define.compiler.validator.reference_graph import reference_graph_validator

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.association_resolution import concrete_program
    from define.compiler.errors import diagnostics
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import program_validator


class CompilerValidationResult(msgspec.Struct):
    """Result of completing every compiler validation stage."""

    program_validation: validation_result.ProgramValidationResult
    concrete_program: concrete_program.ConcreteProgram

    def error_strings(self) -> list[str]:
        """Format errors from the detailed program validation data."""
        return self.program_validation.error_strings()


def validate_and_resolve_program(
    program: program_validator.StructurallyValidatedProgram,
    *,
    max_workers: int | None = None,
    allow_entry_action_occupied_implied_position_requirements: bool = False,
) -> CompilerValidationResult:
    """Run reference graph validation and association resolution on a structurally validated program, loading what resolution chooses, and produce the compiler result.

    allow_entry_action_occupied_implied_position_requirements exists only for
    validation tests of behavior that requires such a program.
    """
    program_result = program.result
    tables = association_tables.AssociationTables(
        program.project_roots(), program_result.source_map
    )
    resolver = association_resolver.AssociationResolver(
        program_result.definitions, tables
    )
    validation = reference_graph_validator.ReferenceGraphValidator(
        program_result.definition_order,
        program_result.definitions,
        program_result.structural_results,
        entry_action=program_result.entry_action,
        allow_entry_action_occupied_implied_position_requirements=(
            allow_entry_action_occupied_implied_position_requirements
        ),
    ).validate(max_workers=max_workers)
    found_diagnostics = validation.diagnostics
    abstract_definitions = validation.abstract_definitions

    def resolve(definition: ast.GlobalDefinition) -> list[diagnostics.Diagnostic]:
        abstract = abstract_definitions.get(definition.typed_name.full_typed_name)
        # A Value Operation whose steps validation could not work out has
        # nothing to resolve.
        if abstract is None:
            return []
        return resolver.resolve(abstract)

    # TODO: Resolve each definition as soon as it and what it references are
    # validated, instead of after validating every definition (commit 7c).
    for resolution_diagnostics in reference_graph_executor.process_definitions(
        program_result.definition_order,
        reference_graph_validator.requires_validation,
        resolve,
        max_workers=max_workers,
    ):
        found_diagnostics.extend(resolution_diagnostics)
    program.load_associated(resolver.chosen_edges(), max_workers=max_workers)
    # The structural run's state, such as its resolver and loaded paths, would
    # otherwise be retained until code generation, but nothing loads more of
    # the program after this.
    del program
    program_result.diagnostics.extend(found_diagnostics)
    program_result.diagnostics.extend(
        resolver.resolve_encoding_operations(program_result.encoding_operations)
    )
    program_result.diagnostics.extend(tables.config_diagnostics())
    return CompilerValidationResult(
        program_validation=program_result,
        concrete_program=resolver.concrete_program(program_result.definition_order),
    )
