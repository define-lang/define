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
        self._definitions: ChainMap[str, ast.LocalPositionDefinition] = ChainMap({})
        self._constraint_names: ChainMap[str, frozenset[str]] = ChainMap({})
        self._enclosing_fqun: ast.Fqun = enclosing_fqun

    def enter_child_scope(self):
        """Push a new child scope layer for nested blocks."""
        self._definitions = self._definitions.new_child({})
        self._constraint_names = self._constraint_names.new_child({})

    def add_local_definition(self, local_def: ast.LocalPositionDefinition):
        """Add a local position definition to scope, pre-computing constraint names."""
        name = local_def.local_name.name
        self._definitions[name] = local_def
        if local_def.constraints is not None:
            self._constraint_names[name] = frozenset(
                req.typed_global_name.full_typed_name(in_universe=self._enclosing_fqun)
                for req in local_def.constraints.requirements
            )
        else:
            self._constraint_names[name] = frozenset()

    def get_definition(self, name: str) -> ast.LocalPositionDefinition | None:
        """Return the definition for a name, or None if not defined."""
        return self._definitions.get(name)

    def is_defined(self, name: ast.TypedName) -> bool:
        """Check if a typed name reference is defined in scope."""
        return name.name_content.full_name() in self._definitions

    def definition_has_quality(
        self, parent: ast.TypedName, quality: ast.TypedName
    ) -> bool:
        """Check if a quality is declared in the parent's constraints."""
        parent_name = parent.name_content.full_name()
        quality_name = quality.full_typed_name(in_universe=self._enclosing_fqun)
        return quality_name in self._constraint_names[parent_name]
