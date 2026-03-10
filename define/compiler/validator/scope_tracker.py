"""Scope tracking for locally-defined positions and their constraints."""

from __future__ import annotations

import typing
from collections import ChainMap

if typing.TYPE_CHECKING:
    from define.compiler import ast


class ScopeTracker:
    """Tracks locally-defined positions and their constraints within an action block."""

    def __init__(self, enclosing_fqun: ast.Fqun):
        """Initialize with the FQUN of the enclosing definition."""
        self._definitions: ChainMap[str, ast.AnyPositionDefinition] = ChainMap()
        self._constraint_names: ChainMap[str, frozenset[str]] = ChainMap()
        self._enclosing_fqun: ast.Fqun = enclosing_fqun

    def enter_child_scope(self):
        """Push a new child scope layer for nested blocks."""
        self._definitions = self._definitions.new_child()
        self._constraint_names = self._constraint_names.new_child()

    def add_definition(self, definition: ast.AnyPositionDefinition):
        """Add a position definition to scope, pre-computing constraint names."""
        key = definition.typed_name.full_typed_name()
        self._definitions[key] = definition
        if definition.constraints is not None:
            self._constraint_names[key] = frozenset(
                req.typed_global_name.full_typed_name(in_universe=self._enclosing_fqun)
                for req in definition.constraints.requirements
            )
        else:
            self._constraint_names[key] = frozenset()

    def defined_on_line(self, typed_name: ast.TypedName) -> int:
        """Return the line where a typed name was defined."""
        key = typed_name.full_typed_name(in_universe=self._enclosing_fqun)
        return self._definitions[key].position.line

    def is_defined(self, name: ast.TypedName) -> bool:
        """Check if a typed name reference is defined in scope."""
        key = name.full_typed_name(in_universe=self._enclosing_fqun)
        return key in self._definitions

    def is_defined_in_current_scope(self, name: ast.TypedName) -> bool:
        """Check if a typed name reference is defined in the current (innermost) scope only."""
        key = name.full_typed_name(in_universe=self._enclosing_fqun)
        return key in self._definitions.maps[0]

    def get_constraint_names(self, name: ast.TypedName) -> frozenset[str]:
        """Return the constraint names for a position, or empty if unconstrained."""
        key = name.full_typed_name(in_universe=self._enclosing_fqun)
        return self._constraint_names.get(key, frozenset())

    def definition_has_quality(
        self, parent: ast.TypedName, quality: ast.TypedName
    ) -> bool:
        """Check if a quality is declared in the parent's constraints."""
        parent_key = parent.full_typed_name(in_universe=self._enclosing_fqun)
        quality_name = quality.full_typed_name(in_universe=self._enclosing_fqun)
        return quality_name in self._constraint_names[parent_key]
