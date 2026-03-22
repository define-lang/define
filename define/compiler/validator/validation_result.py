"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import (
    action_call_graph,
    ast,
    diagnostics,
    exceptions,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping, Sequence

    from define.compiler.validator import reference_graph, stats

type AnyValidationException = exceptions.DefineError | lark_standalone.UnexpectedInput


@dataclass
class DiscoveredFile:
    """A file discovered during validation that should be validated next."""

    path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    position: ast.SourcePosition


@dataclass(frozen=True)
class DeferredChainElements:
    """The remaining sub-section of a chained name that needs deferred validation against a global name's definition."""

    enclosing_definition: ast.QualityDefinition
    parent_element: ast.GlobalTypedNameReference
    chain_element: ast.TypedNameReference
    remaining_chain: ast.ChainedName

    @property
    def source_fqun(self) -> ast.Fqun:
        """Return the FQUN of the enclosing definition."""
        return self.enclosing_definition.typed_name.name_content.fqun

    @cached_property
    def parent_full_typed_name(self) -> str:
        """Return the fully qualified typed-name key for the parent element."""
        return self.parent_element.full_typed_name(in_universe=self.source_fqun)

    def next_deferred(
        self,
        validated_element: ast.GlobalTypedNameReference,
        remaining: ast.ChainedName,
    ) -> DeferredChainElements:
        """Create the next deferred element after validating one in the chain."""
        chain_element = remaining.typed_names[0]
        del remaining.typed_names[0]
        return DeferredChainElements(
            enclosing_definition=self.enclosing_definition,
            parent_element=validated_element,
            chain_element=chain_element,
            remaining_chain=remaining,
        )


@dataclass(frozen=True)
class DimensionPointStatementValidity:
    """Name validation results for a create or move statement."""

    statement: ast.DimensionPointStatement
    source_ok: bool
    target_ok: bool


@dataclass
class DefinitionValidationResult:
    """Validation output for one definition within a file."""

    definition: ast.QualityDefinition
    _diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)

    reference_edges: list[reference_graph.ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
    deferred_chained_names: list[DeferredChainElements] = field(default_factory=list)
    trigger_positions: list[action_call_graph.TriggerPositionInfo] = field(
        default_factory=list
    )
    action_body_effects: list[action_call_graph.ActionBodyEffect] = field(
        default_factory=list
    )
    dp_statement_validity: list[DimensionPointStatementValidity] = field(
        default_factory=list
    )

    def add_diagnostic(self, diagnostic: diagnostics.Diagnostic):
        """Append a diagnostic to this definition's results."""
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return diagnostics sorted by source position (line, then column)."""
        return sorted(
            self._diagnostics,
            key=lambda d: (d.position.line, d.position.column),
        )

    @property
    def position_constraint_names(self) -> frozenset[str]:
        """Return required qualities when this definition is a global position."""
        definition = self.definition
        if not isinstance(definition, ast.PositionDefinition):
            return frozenset()
        if definition.constraints is None:
            return frozenset()
        fqun = definition.typed_name.name_content.fqun
        return frozenset(
            requirement.typed_global_name.full_typed_name(in_universe=fqun)
            for requirement in definition.constraints.requirements
        )

    @property
    def action_local_position_constraint_names(
        self,
    ) -> Mapping[str, frozenset[str]]:
        """Return local position constraints when this definition is an action."""
        definition = self.definition
        if not isinstance(definition, ast.ActionDefinition):
            return {}
        if definition.definition_block is None:
            return {}
        fqun = definition.typed_name.name_content.fqun
        result: dict[str, frozenset[str]] = {}
        for local_def in definition.definition_block.interface_positions:
            local_name = local_def.typed_name.name_content.name
            if local_name in result:
                continue
            if local_def.constraints is None:
                result[local_name] = frozenset()
                continue
            result[local_name] = frozenset(
                requirement.typed_global_name.full_typed_name(in_universe=fqun)
                for requirement in local_def.constraints.requirements
            )
        return result


@dataclass
class FileValidationResult:
    """Validation output for one source file."""

    exception: AnyValidationException | None
    source: str | None
    file_path: pathlib.PurePosixPath  # Full path: root_prefix / relative file path.
    root_prefix: pathlib.PurePosixPath
    stats: stats.ValidationTimingStats
    file_diagnostics: list[diagnostics.Diagnostic]
    _post_definition_diagnostics: list[diagnostics.Diagnostic] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    # This preserves source order, including duplicate definitions that were
    # diagnosed during file validation.
    definition_results: list[DefinitionValidationResult]

    def add_file_diagnostic(self, diagnostic: diagnostics.Diagnostic):
        """Append a non-definition diagnostic after per-definition diagnostics."""
        self._post_definition_diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> Sequence[diagnostics.Diagnostic]:
        """Return file-level and per-definition diagnostics as a read-only view."""
        return (
            list(self.file_diagnostics)
            + [
                diagnostic
                for result in self.definition_results
                for diagnostic in result.diagnostics
            ]
            + list(self._post_definition_diagnostics)
        )


@dataclass
class ProgramValidationResult:
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    action_call_graph: action_call_graph.ActionCallGraph
    config_loading_time_ns: int
    reference_graph: reference_graph.ReferenceGraph

    @property
    def all_diagnostics(self) -> list[diagnostics.Diagnostic]:
        """All diagnostics from all file results."""
        return [d for r in self.file_results for d in r.diagnostics]

    @property
    def all_exceptions(self) -> list[AnyValidationException]:
        """All exceptions from all file results."""
        return [r.exception for r in self.file_results if r.exception is not None]

    def has_errors(self) -> bool:
        """Whether any file had exceptions or diagnostics."""
        return bool(self.all_exceptions or self.all_diagnostics)
