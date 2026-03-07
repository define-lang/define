"""Shared data types for Define language validation."""

from __future__ import annotations

import collections
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
    from collections.abc import Set

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
    chain_element: ast.TypedName
    remaining_chain: list[ast.TypedName]

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
        remaining: list[ast.TypedName],
    ) -> DeferredChainElements:
        """Create the next deferred element after validating one in the chain."""
        return DeferredChainElements(
            enclosing_definition=self.enclosing_definition,
            parent_element=validated_element,
            chain_element=remaining[0],
            remaining_chain=remaining[1:],
        )


@dataclass(frozen=True)
class TriggerPositionInfo:
    """An action's trigger condition, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    checked_position: list[ast.TypedName]

    @cached_property
    def checked_position_name_with_prefix(self) -> str:
        """Return the full chained name of the position the trigger condition is checking, prefixed with the action name."""
        fqun = self.enclosing_typed_name.name_content.fqun
        chain_str = "::".join(
            elem.full_typed_name(in_universe=fqun) for elem in self.checked_position
        )
        return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"


@dataclass(frozen=True)
class ActionBodyEffect:
    """A body statement that writes a DP into a position, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    statement: ast.CreateDimensionPointStatement | ast.MoveDimensionPointStatement

    @property
    def modified_position(self) -> list[ast.TypedName]:
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
        chain = self.modified_position
        fqun = self.enclosing_typed_name.name_content.fqun
        for i in range(len(chain) - 1, -1, -1):
            elem = chain[i]
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
        chain = self.modified_position
        fqun = self.enclosing_typed_name.name_content.fqun
        boundary = self._action_boundary
        if boundary is None:
            chain_str = "::".join(
                elem.full_typed_name(in_universe=fqun) for elem in chain
            )
            return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"
        idx = boundary[0]
        return "::".join(elem.full_typed_name(in_universe=fqun) for elem in chain[idx:])


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


# TODO: Rename This FileValidationResult and create another class for the ProgramValidationResult.
@dataclass
class ValidationResult:
    """Validation output for one source file."""

    diagnostics: list[diagnostics.Diagnostic]
    exception: AnyValidationException | None
    source: str | None
    file_path: pathlib.PurePosixPath  # Full path: root_prefix / relative file path.
    root_prefix: pathlib.PurePosixPath
    stats: stats.ValidationTimingStats
    # TODO: There's soooo much stuff here from ProgramAstValidator, maybe
    # we should put it into its own type.
    definitions: list[ast.QualityDefinition] = field(default_factory=list)
    reference_edges: list[ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
    deferred_chained_names: list[DeferredChainElements] = field(default_factory=list)
    trigger_positions: list[TriggerPositionInfo] = field(default_factory=list)
    action_body_effects: list[ActionBodyEffect] = field(default_factory=list)
    deferred_move_constraint_checks: list[DeferredMoveConstraintCheck] = field(
        default_factory=list
    )

    @cached_property
    def definitions_by_name(self) -> dict[str, ast.QualityDefinition]:
        """Map from full typed name to definition."""
        return {d.typed_name.full_typed_name(): d for d in self.definitions}

    @cached_property
    def global_position_definition_constraints(
        self,
    ) -> collections.defaultdict[str, frozenset[str]]:
        """Map from definition name to the set of its constraint typed names."""
        result: collections.defaultdict[str, frozenset[str]] = collections.defaultdict(
            frozenset
        )
        for d in self.definitions:
            if not isinstance(d, ast.PositionDefinition):
                continue
            fqun = d.typed_name.name_content.fqun
            if d.constraints is not None:
                result[d.typed_name.full_typed_name()] = frozenset(
                    req.typed_global_name.full_typed_name(in_universe=fqun)
                    for req in d.constraints.requirements
                )
            else:
                result[d.typed_name.full_typed_name()] = frozenset()
        return result

    @cached_property
    def action_local_position_constraints(
        self,
    ) -> collections.defaultdict[str, dict[str, frozenset[str]]]:
        """Map from action name to its local positions' constraint sets.

        Outer key: action definition full typed name.
        Inner key: local position name.
        Inner value: frozenset of constraint typed names for that local position.
        """
        result: collections.defaultdict[str, dict[str, frozenset[str]]] = (
            collections.defaultdict(dict)
        )
        for d in self.definitions:
            if not isinstance(d, ast.ActionDefinition):
                continue
            if d.definition_block is None:
                continue
            fqun = d.typed_name.name_content.fqun
            locals_map: dict[str, frozenset[str]] = {}
            for local_def in d.definition_block.local_definitions:
                if local_def.constraints is not None:
                    locals_map[local_def.typed_name.name_content.name] = frozenset(
                        req.typed_global_name.full_typed_name(in_universe=fqun)
                        for req in local_def.constraints.requirements
                    )
                else:
                    locals_map[local_def.typed_name.name_content.name] = frozenset()
            result[d.typed_name.full_typed_name()] = locals_map
        return result
