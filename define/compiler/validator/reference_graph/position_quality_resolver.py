"""Resolve the Qualities required at Positions."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.validator.reference_graph import quality_assignment

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        reference_graph_validation_state,
    )


class PositionQualityResolver:
    """Resolve Position Constraints and their transitive Quality implications."""

    _definition: ast.ActionDefinition
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState

    def __init__(
        self,
        definition: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Initialize with the current Action Definition, known definitions, and shared cache."""
        self._definition = definition
        self._definition_results = definition_results
        self._validation_state = validation_state

    def get_direct_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> tuple[
        tuple[ast.GlobalTypedNameReference, ...] | None,
        tuple[str, ...] | None,
    ]:
        """Resolve the constraint qualities required at a position, in source order.

        Also returns the cache key identifying the cacheable entity (a
        global position or an action interface position), or ``None``
        for local positions defined inside of an Action Statements Block.
        """
        if scope.is_defined_local(position):
            # is_defined_local already verified the chain is a single LocalTypedNameReference.
            local_name = typing.cast(
                "ast.LocalTypedNameReference", position.typed_names[0]
            )
            definition = scope.get_definition(local_name)
            return (
                definition.constraint_typed_names,
                self._local_definition_cache_key(local_name),
            )

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface position definition. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position.
            parent = typing.cast(
                "ast.GlobalTypedNameReference", position.typed_names[-2]
            )
            action_def = self._definition_results[parent].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return (
                action_def.interface_positions_by_name[
                    last_element.full_typed_name
                ].constraint_typed_names,
                (parent.full_typed_name, last_element.full_typed_name),
            )

        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(last_element)
        if definition_result is None:
            return (None, None)
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return (position_def.constraint_typed_names, (last_element.full_typed_name,))

    def get_transitive_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> quality_assignment.QualityAssignments:
        """Resolve required Qualities and their implications in assignment order."""
        direct, cache_key = self.get_direct_required_qualities(position, scope)
        if direct is None:
            return quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
        if cache_key is None:
            return self._build_quality_assignments(direct)
        return self._validation_state.get_or_build_quality_assignments(
            cache_key, lambda: self._build_quality_assignments(direct)
        )

    def _build_quality_assignments(
        self, direct: tuple[ast.GlobalTypedNameReference, ...]
    ) -> quality_assignment.QualityAssignments:
        """Build assigned qualities in source-order depth-first assignment order."""

        def implications_for(
            typed_name: ast.GlobalTypedNameReference,
        ) -> tuple[ast.GlobalTypedNameReference, ...]:
            defn_result = self._definition_results.get(typed_name)
            if defn_result is None:
                return ()
            return tuple(
                implication.typed_global_name
                for implication in defn_result.definition.quality_implications
            )

        return quality_assignment.QualityAssignments.expand_implications(
            direct, implications_for
        )

    def _local_definition_cache_key(
        self,
        local_name: ast.LocalTypedNameReference,
    ) -> tuple[str, ...] | None:
        """Cache interface positions so the action's own processing fills the same key external references use."""
        if local_name.full_typed_name in self._definition.interface_positions_by_name:
            return (
                self._definition.typed_name.full_typed_name,
                local_name.full_typed_name,
            )
        return None
