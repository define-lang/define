"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import (
    ast,
    diagnostics,
    exceptions,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping, Sequence, Set

    from define.compiler.validator import stats

type AnyValidationException = exceptions.DefineError | lark_standalone.UnexpectedInput


@dataclass
class DiscoveredFile:
    """A file discovered during validation that should be validated next."""

    path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    position: ast.SourcePosition


@dataclass(frozen=True)
class ReferenceEdge:
    """A reference from one definition to a global name in another file."""

    enclosing_definition: ast.QualityDefinition
    global_name_reference: ast.GlobalTypedNameReference

    @cached_property
    def full_typed_name(self) -> str:
        """Return the fully qualified typed-name key for this edge target."""
        return self.global_name_reference.full_typed_name(
            in_universe=self.enclosing_definition.typed_name.name_content.fqun
        )


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
class TriggerPositionInfo:
    """An action's trigger condition, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    checked_position: ast.ChainedName

    @cached_property
    def checked_position_name_with_prefix(self) -> str:
        """Return the full chained name of the position the trigger condition is checking, prefixed with the action name."""
        fqun = self.enclosing_typed_name.name_content.fqun
        chain_str = self.checked_position.canonical_chained_name(in_universe=fqun)
        return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"


@dataclass(frozen=True)
class ActionBodyEffect:
    """A body statement that writes a DP into a position, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    statement: ast.CreateDimensionPointStatement | ast.MoveDimensionPointStatement

    @property
    def modified_position(self) -> ast.ChainedName:
        """Return the position chain that this statement writes into."""
        match self.statement:
            case ast.CreateDimensionPointStatement():
                return self.statement.position_reference.chain
            case ast.MoveDimensionPointStatement():
                return self.statement.to_position.chain

    @cached_property
    def _action_boundary(self) -> tuple[int, str] | None:
        """Find the last action reference in the chain.

        Returns (index, full_typed_name) or None if no action ref exists.
        """
        fqun = self.enclosing_typed_name.name_content.fqun
        for i in range(len(self.modified_position.typed_names) - 1, -1, -1):
            elem = self.modified_position.typed_names[i]
            if elem.name_type == ast.NameType.ACTION:
                return (i, elem.full_typed_name(in_universe=fqun))
        return None

    @cached_property
    def target_action_name(self) -> str:
        """Return the action whose position is being modified.

        When the chain contains an explicit action reference, that action is
        the target. Otherwise, the enclosing action is the implicit target
        (the write is to a local position).
        """
        if self._action_boundary is not None:
            return self._action_boundary[1]
        return self.enclosing_typed_name.full_typed_name()

    @cached_property
    def affected_position_qualified_chained_name(self) -> str:
        """Return the globally-unique position key of the position that was affected (got a dimension point)."""
        fqun = self.enclosing_typed_name.name_content.fqun
        boundary = self._action_boundary
        if boundary is None:
            chain_str = self.modified_position.canonical_chained_name(in_universe=fqun)
            return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"
        idx = boundary[0]
        return "::".join(
            elem.full_typed_name(in_universe=fqun)
            for elem in self.modified_position.typed_names[idx:]
        )


@dataclass
class DeferredMoveConstraintCheck:
    """A move constraint check deferred because at least one position is a chained name.

    Whichever of from_qualities/to_qualities is None will be resolved by the
    program validator from the chained position's definition constraints.
    The check executes once both are resolved.
    """

    enclosing_definition: ast.QualityDefinition
    statement: ast.MoveDimensionPointStatement
    from_qualities: Set[str] | None
    to_qualities: Set[str] | None


@dataclass
class DefinitionValidationResult:
    """Validation output for one definition within a file."""

    definition: ast.QualityDefinition
    _diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)

    reference_edges: list[ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
    deferred_chained_names: list[DeferredChainElements] = field(default_factory=list)
    trigger_positions: list[TriggerPositionInfo] = field(default_factory=list)
    action_body_effects: list[ActionBodyEffect] = field(default_factory=list)
    deferred_move_constraint_checks: list[DeferredMoveConstraintCheck] = field(
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
        for local_def in definition.definition_block.local_definitions:
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
class ValidationResult:
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
