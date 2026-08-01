"""Scope tracking for locally-defined positions within an action block."""

from __future__ import annotations

import typing
from collections import ChainMap
from typing import TYPE_CHECKING

from define.compiler import ast

if TYPE_CHECKING:
    from collections.abc import Reversible


class ScopeTracker:
    """Tracks locally-defined positions within an action block."""

    def __init__(self):
        """Initialize an empty scope tracker."""
        self._definitions: ChainMap[str, ast.LocalPositionDefinition] = ChainMap()

    def enter_child_scope(self):
        """Push a new child scope layer for nested blocks."""
        self._definitions = self._definitions.new_child()

    def add_definition(self, definition: ast.LocalPositionDefinition):
        """Add a position definition to scope."""
        key = definition.typed_name.source_typed_name
        self._definitions[key] = definition

    def current_scope_definitions(self) -> Reversible[ast.LocalPositionDefinition]:
        """Return the position definitions added directly to the current (innermost) scope, in insertion order."""
        # ChainMap.maps is typed as list[MutableMapping[...]], whose .values()
        # returns a non-reversible ValuesView. In practice every layer is a real
        # dict (ChainMap initializes maps[0] = {} and new_child() defaults the
        # same way), so the underlying dict_values does support __reversed__.
        inner = typing.cast(
            "dict[str, ast.LocalPositionDefinition]", self._definitions.maps[0]
        )
        return inner.values()

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

    def get_definition(self, name: ast.TypedName) -> ast.LocalPositionDefinition:
        """Return the position definition for a typed name."""
        return self._definitions[name.full_typed_name]
