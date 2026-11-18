"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass

import msgspec

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.association_resolution import concrete_program
    from define.compiler.data_structures import define_path, typed_name_dict
    from define.compiler.errors import syntax_errors
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
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic]


class ActionPostorderValidationResult(PostorderValidationResult):
    """Result of validating a single action definition during the DFS post-order walk."""

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
    """Result of validating a single Encoding Operation definition during the DFS post-order walk."""

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


class DefinitionDiagnostics(msgspec.Struct, frozen=True):
    """The diagnostics that a stage after structural validation found about one definition, which are added to its result once the stage finishes."""

    definition: ast.GlobalDefinition
    diagnostics: list[diagnostics.Diagnostic]


def add_definition_diagnostics(
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        DefinitionValidationResult,
    ],
    stage_diagnostics: Iterable[DefinitionDiagnostics],
):
    """Add the diagnostics that a stage found to the results of the definitions they are about."""
    for found in stage_diagnostics:
        definition_results[found.definition.typed_name].diagnostics.extend(
            found.diagnostics
        )


@dataclass
class FileValidationResult:
    """Validation output for one source file."""

    # The diagnostic that kept the file from loading or parsing, if any.
    load_failure: syntax_errors.FileLoadFailureDiagnostic | None
    file_path: define_path.DefinePath  # Full path: root_prefix / relative file path.
    root_prefix: define_path.DefinePath
    file_diagnostics: list[diagnostics.Diagnostic]
    # The file's validated definitions, in source order.
    definition_results: list[DefinitionValidationResult]

    @property
    def diagnostics(self) -> Sequence[diagnostics.BaseDiagnostic]:
        """The load failure, if any, then the file-level and per-definition diagnostics sorted by source location (line, then column)."""
        located_diagnostics = list(self.file_diagnostics)
        for result in self.definition_results:
            located_diagnostics.extend(result.diagnostics)
        located_diagnostics.sort(key=lambda d: (d.location.line, d.location.column))
        if self.load_failure is None:
            return located_diagnostics
        return [self.load_failure, *located_diagnostics]


class ProgramValidationResult(msgspec.Struct):
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    entry_action: ast.ActionDefinition | None
    definition_order: reference_graph_order.ReferenceGraphOrder
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        DefinitionValidationResult,
    ]
    # The diagnostics about the program rather than one of its files: the
    # entry file path's, and those of every project config that was loaded,
    # each reported once however many files depend on its config.
    program_diagnostics: list[diagnostics.FormattableDiagnostic]
    source_map: rendering.SourceMap

    @property
    def all_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """The program diagnostics sorted by file and location, then all diagnostics from all file results."""
        all_diagnostics = sorted(
            self.program_diagnostics, key=_program_diagnostic_order
        )
        for result in self.file_results:
            all_diagnostics.extend(result.diagnostics)
        return all_diagnostics

    def error_strings(self) -> list[str]:
        """Format every diagnostic for the command-line caller."""
        return [
            diagnostic.format(self.source_map) for diagnostic in self.all_diagnostics
        ]

    def has_errors(self) -> bool:
        """Whether the program has any diagnostics."""
        # Every diagnostic is an error, which keeps code generation from ever
        # running on a file whose comments have characters the spec does not
        # allow, such as the bidi controls of a Trojan Source attack.
        return bool(self.all_diagnostics)


def _program_diagnostic_order(
    diagnostic: diagnostics.FormattableDiagnostic,
) -> tuple[str, int, int]:
    """Return a program diagnostic's file and its line and column in that file, by which program diagnostics are sorted."""
    if isinstance(diagnostic, diagnostics.Diagnostic):
        location = diagnostic.location
        return (location.file_path or "", location.line, location.column)
    # A diagnostic about a whole config file comes before the diagnostics at
    # places in it.
    if isinstance(diagnostic, diagnostics.ConfigDiagnostic):
        return (diagnostic.config_path, 0, 0)
    # The rest are about the whole program, such as its entry path, and come
    # first, in the order they were found.
    return ("", 0, 0)
