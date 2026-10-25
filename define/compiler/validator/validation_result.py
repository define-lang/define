"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass

import msgspec

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from define.compiler import ast
    from define.compiler.data_structures import define_path, typed_name_dict
    from define.compiler.errors import diagnostics, exceptions, source_map
    from define.compiler.graphs import reference_graph, reference_graph_order
    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph import action_contract


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

    exception: exceptions.DefineError | None
    # The digest of a file that was read from the filesystem, which lets a
    # source map read it again for diagnostics without keeping its text.
    source_digest: bytes | None
    file_path: define_path.DefinePath  # Full path: root_prefix / relative file path.
    root_prefix: define_path.DefinePath
    file_diagnostics: list[diagnostics.Diagnostic]
    # This preserves source order, including duplicate definitions that were
    # diagnosed during file validation.
    definition_results: list[DefinitionValidationResult]

    @property
    def diagnostics(self) -> Sequence[diagnostics.Diagnostic]:
        """File-level and per-definition diagnostics, sorted by source location (line, then column)."""
        all_diagnostics = list(self.file_diagnostics)
        for result in self.definition_results:
            all_diagnostics.extend(result.diagnostics)
        all_diagnostics.sort(key=lambda d: (d.location.line, d.location.column))
        return all_diagnostics

    def edges_to_other_files(self) -> Iterator[reference_graph.ReferenceEdge]:
        """Yield the edges that lead to other files.

        An edge leads to another file unless its target is the enclosing
        definition or a definition that appeared earlier in the same file.
        """
        seen_targets: set[str] = set()
        for definition_result in self.definition_results:
            seen_targets.add(definition_result.definition.typed_name.full_typed_name)
            for edge in definition_result.reference_edges:
                if edge.target_full_typed_name not in seen_targets:
                    yield edge

    def first_edge_per_referenced_file(
        self,
    ) -> Iterator[reference_graph.ReferenceEdge]:
        """Yield each definition's first edge per referenced file.

        Within one definition, only the first reference to a given file drives
        file loading and its diagnostics, no matter which definition type the
        references name.
        """
        seen_targets: set[str] = set()
        for definition_result in self.definition_results:
            seen_targets.add(definition_result.definition.typed_name.full_typed_name)
            seen_files: set[tuple[str, str]] = set()
            for edge in definition_result.reference_edges:
                if edge.target_full_typed_name in seen_targets:
                    continue
                referenced_file = (
                    edge.global_name_reference.effective_fqun.canonical,
                    edge.global_name_reference.name_content.path.name,
                )
                if referenced_file in seen_files:
                    continue
                seen_files.add(referenced_file)
                yield edge


class ProgramValidationResult(msgspec.Struct):
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    entry_action: ast.ActionDefinition | None
    definition_order: reference_graph_order.ReferenceGraphOrder
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        DefinitionValidationResult,
    ]
    source_map: source_map.SourceMap

    @property
    def all_diagnostics(self) -> list[diagnostics.Diagnostic]:
        """All diagnostics from all file results."""
        return [d for r in self.file_results for d in r.diagnostics]

    @property
    def all_exceptions(self) -> list[exceptions.DefineError]:
        """All exceptions from all file results."""
        return [r.exception for r in self.file_results if r.exception is not None]

    def has_errors(self) -> bool:
        """Whether any file had exceptions or diagnostics."""
        # Every diagnostic is an error, which keeps code generation from ever
        # running on a file whose comments have characters the spec does not
        # allow, such as the bidi controls of a Trojan Source attack.
        return bool(self.all_exceptions or self.all_diagnostics)
