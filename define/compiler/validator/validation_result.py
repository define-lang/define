"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass

import msgspec

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast
    from define.compiler.data_structures import define_path, typed_name_dict
    from define.compiler.errors import diagnostics
    from define.compiler.graphs import reference_graph, reference_graph_order
    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph import action_contract
    from source_rendering.python import rendering


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
    codegen_input: codegen_input.ActionCodegenInput


class LogicalOperationPostorderValidationResult(PostorderValidationResult):
    """Result of validating a logical operation definition during the DFS post-order walk."""

    # The Encoding Operations that perform the logical operation, keyed by the
    # full typed names of the encodings of their views, in the order of the
    # logical operation's views.
    encoding_operations: dict[tuple[str, ...], ast.EncodingOperationDefinition]


class EncodingOperationPostorderValidationResult(PostorderValidationResult):
    """Result of validating a single Encoding Operation definition during the DFS post-order walk."""

    codegen_input: codegen_input.EncodingOperationCodegenInput


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


@dataclass
class FileValidationResult:
    """Validation output for one source file."""

    # The diagnostic that kept the file from loading or parsing, if any.
    load_failure: diagnostics.FileLoadFailureDiagnostic | None
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
        """The program diagnostics, then all diagnostics from all file results."""
        all_diagnostics = list(self.program_diagnostics)
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
