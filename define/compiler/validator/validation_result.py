"""Shared data types for Define language validation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.association_resolution import concrete_program
    from define.compiler.data_structures import define_path
    from define.compiler.graphs import reference_graph, reference_graph_order
    from define.compiler.validator.reference_graph import (
        abstract_program,
        action_contract,
    )


class ParticleStatementValidity(msgspec.Struct, frozen=True):
    """Name validation results for a Particle Statement."""

    target_ok: bool
    source_ok: bool = True
    from_is_prefix_of_to: bool = False


class PostorderValidationResult(msgspec.Struct):
    """Result of validating a single definition after everything it directly references is validated."""

    diagnostics: list[diagnostics.Diagnostic]


class ActionPostorderValidationResult(PostorderValidationResult):
    """Result of validating a single action definition after everything it directly references is validated."""

    contract: action_contract.ActionContract
    action: abstract_program.AbstractAction


class ValueOperationPostorderValidationResult(PostorderValidationResult):
    """Result of validating a Value Operation definition."""

    # None when either validation phase reported anything about the Value
    # Operation, because its steps may then be incomplete or refer to views
    # that do not exist, and nothing executing it can choose Encoding
    # Operations from them.
    steps: list[abstract_program.ValueOperationStep] | None


class EncodingOperationPostorderValidationResult(PostorderValidationResult):
    """Result of validating a single Encoding Operation definition."""

    encoding_operation: concrete_program.ConcreteEncodingOperation


class DefinitionValidationResult(msgspec.Struct):
    """Validation output for one definition within a file."""

    definition: ast.GlobalDefinition
    diagnostics: list[diagnostics.Diagnostic] = msgspec.field(default_factory=list)

    reference_edges: list[reference_graph.ReferenceEdge] = msgspec.field(
        default_factory=list
    )
    particle_statement_validity: list[ParticleStatementValidity] = msgspec.field(
        default_factory=list
    )
    # Whether each position looked at by an Operation Argument Statement in an
    # action is valid, in source order.
    looked_at_position_validity: list[bool] = msgspec.field(default_factory=list)


class FileValidationResult(msgspec.Struct):
    """Validation output for one source file."""

    file_path: define_path.DefinePath  # Full path: root_prefix / relative file path.
    root_prefix: define_path.DefinePath
    # The file's validated definitions, in source order.
    definition_results: list[DefinitionValidationResult]


class ProgramValidationResult(msgspec.Struct):
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    entry_action: ast.ActionDefinition | None
    definition_order: reference_graph_order.ReferenceGraphOrder
    # Each validated definition, by its full typed name.
    definitions: dict[str, ast.GlobalDefinition]
    # The result of each validated definition, by its full typed name, which
    # reference graph validation reads for each action and Value Operation
    # that it validates.
    structural_results: dict[str, DefinitionValidationResult]
    # Each validated Encoding Operation, which association resolution
    # validates once the ones it chooses are loaded.
    encoding_operations: list[ast.EncodingOperationDefinition]
    # Every diagnostic about the program, from every stage, in the order each
    # stage found them.
    diagnostics: list[diagnostics.FormattableDiagnostic]
    source_map: rendering.SourceMap

    def sorted_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Every diagnostic, sorted by file and location, after those that have no location in the order they were found."""
        return sorted(self.diagnostics, key=_diagnostic_order)

    def error_strings(self) -> list[str]:
        """Format every diagnostic for the command-line caller."""
        return [
            diagnostic.format(self.source_map)
            for diagnostic in self.sorted_diagnostics()
        ]

    def has_errors(self) -> bool:
        """Whether the program has any diagnostics."""
        # Every diagnostic is an error, which keeps code generation from ever
        # running on a file whose comments have characters the spec does not
        # allow, such as the bidi controls of a Trojan Source attack.
        return bool(self.diagnostics)


def _diagnostic_order(
    diagnostic: diagnostics.FormattableDiagnostic,
) -> tuple[str, int, int]:
    """Return a diagnostic's file and its line and column in that file, by which diagnostics are sorted."""
    if isinstance(diagnostic, diagnostics.Diagnostic):
        location = diagnostic.location
        return (location.file_path or "", location.line, location.column)
    # A diagnostic about a whole config file comes before the diagnostics at
    # places in it.
    if isinstance(diagnostic, diagnostics.ConfigDiagnostic):
        return (diagnostic.config_path, 0, 0)
    # The rest have no location, such as the entry path's diagnostics and a
    # file that cannot be read, and come first, in the order they were found.
    return ("", 0, 0)
