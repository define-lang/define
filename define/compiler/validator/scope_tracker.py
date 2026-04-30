"""Scope tracking for locally-defined positions and their constraints."""

from __future__ import annotations

from collections import ChainMap

from define.compiler import ast


class ScopeTracker:
    """Tracks locally-defined positions and their constraints within an action block."""

    def __init__(self):
        """Initialize an empty scope tracker."""
        self._definitions: ChainMap[str, ast.AnyPositionDefinition] = ChainMap()
        self._constraint_names: ChainMap[str, frozenset[str]] = ChainMap()

    def enter_child_scope(self):
        """Push a new child scope layer for nested blocks."""
        self._definitions = self._definitions.new_child()
        self._constraint_names = self._constraint_names.new_child()

    def add_definition(self, definition: ast.AnyPositionDefinition):
        """Add a position definition to scope, pre-computing constraint names."""
        key = definition.typed_name.source_typed_name
        self._definitions[key] = definition
        if definition.constraints is not None:
            self._constraint_names[key] = frozenset(
                req.typed_global_name.full_typed_name
                for req in definition.constraints.requirements
            )
        else:
            self._constraint_names[key] = frozenset()

    def defined_on_line(self, typed_name: ast.TypedName) -> int:
        """Return the line where a typed name was defined."""
        return self._definitions[typed_name.full_typed_name].location.line

    def is_defined_local(self, position: ast.PositionReference) -> bool:
        """Check if a position reference is a single local name defined in scope."""
        if len(position.typed_names) != 1:
            return False
        first = position.typed_names[0]
        if not isinstance(first, ast.LocalTypedNameReference):
            return False
        return self.is_defined(first)

    def is_defined(self, name: ast.TypedName) -> bool:
        """Check if a typed name reference is defined in scope."""
        return name.full_typed_name in self._definitions

    def is_defined_in_current_scope(self, name: ast.TypedName) -> bool:
        """Check if a typed name reference is defined in the current (innermost) scope only."""
        return name.full_typed_name in self._definitions.maps[0]

    def get_constraint_names(self, name: ast.TypedName) -> frozenset[str]:
        """Return the constraint names for a position, or empty if unconstrained."""
        return self._constraint_names.get(name.full_typed_name, frozenset())

    def get_definition(self, name: ast.TypedName) -> ast.AnyPositionDefinition:
        """Return the position definition for a typed name."""
        return self._definitions[name.full_typed_name]

    # TODO: dead code
    def definition_has_quality(
        self, parent: ast.TypedName, quality: ast.TypedName
    ) -> bool:
        """Check if a quality is declared in the parent's constraints."""
        return quality.full_typed_name in self._constraint_names[parent.full_typed_name]
