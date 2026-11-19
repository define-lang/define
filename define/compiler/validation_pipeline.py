"""The compiler's validation stages, from a structurally validated program to its concrete program, without code generation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import definition_pipeline, work_pool
from define.compiler.association_resolution import association_resolver
from define.compiler.validator.reference_graph import reference_graph_validator

if typing.TYPE_CHECKING:
    from define.compiler.association_resolution import concrete_program
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
    resolver = association_resolver.AssociationResolver(
        program_result.definitions, program.project_roots
    )
    validator = reference_graph_validator.ReferenceGraphValidator(
        program_result.definitions,
        program_result.structural_results,
        entry_action=program_result.entry_action,
        allow_entry_action_occupied_implied_position_requirements=(
            allow_entry_action_occupied_implied_position_requirements
        ),
    )
    with work_pool.WorkPool(max_workers) as pool:
        found_diagnostics = definition_pipeline.DefinitionPipeline(
            program_result.definition_order, validator, resolver, pool
        ).run()
    program.load_associated(resolver.chosen_edges(), max_workers=max_workers)
    # The structural run's state, such as its resolver and loaded paths, would
    # otherwise be retained until code generation, but nothing loads more of
    # the program after this.
    del program
    encoding_operation_diagnostics = resolver.resolve_encoding_operations(
        program_result.encoding_operations
    )
    program_result.diagnostic_lists.extend(
        [found_diagnostics, encoding_operation_diagnostics]
    )
    return CompilerValidationResult(
        program_validation=program_result,
        concrete_program=resolver.concrete_program(program_result.definition_order),
    )
