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


@dataclass
class ValidationResult:
    """Validation output for one source file."""

    diagnostics: list[diagnostics.Diagnostic]
    exception: AnyValidationException | None
    source: str | None
    file_path: pathlib.PurePosixPath  # Full path: root_prefix / relative file path.
    root_prefix: pathlib.PurePosixPath
    stats: stats.ValidationTimingStats
    definitions: list[ast.QualityDefinition] = field(default_factory=list)
    reference_edges: list[ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
    deferred_chained_names: list[DeferredChainElements] = field(default_factory=list)

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
                    locals_map[local_def.local_name.name] = frozenset(
                        req.typed_global_name.full_typed_name(in_universe=fqun)
                        for req in local_def.constraints.requirements
                    )
                else:
                    locals_map[local_def.local_name.name] = frozenset()
            result[d.typed_name.full_typed_name()] = locals_map
        return result
