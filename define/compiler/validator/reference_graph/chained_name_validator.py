"""Validate chained names against Position Constraints and Action Interface Positions."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import particle_tracker


class ChainedNameValidator:
    """Check chained names against the definitions of their parent names."""

    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _tracker: particle_tracker.ParticleTracker

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        tracker: particle_tracker.ParticleTracker,
    ):
        """Initialize with known definitions and the action's particle state."""
        self._definition_results = definition_results
        self._tracker = tracker

    def validate(
        self,
        chain: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> list[diagnostics.Diagnostic]:
        """Validate chained name elements against their parent name's constraints.

        Marks the chain's occupancy state as ERROR in the tracker if validation fails.
        """
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        if len(chain.typed_names) < 2:
            return validation_diagnostics
        elements = chain.typed_names
        first = elements[0]
        # An interface position at index 0 is in scope and provides its own
        # constraints; every other parent name in the chain must be a global
        # definition that we have to look up.
        index = 0
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                chain,
                elements[1],
                scope.get_definition(first).constraints,
                first.full_typed_name,
                validation_diagnostics,
            )
            index = 1

        while index < len(elements) - 1:
            # The file_validator rejects any non-first local in a chain unless
            # it follows a global action, and _validate_action_chain_step
            # consumes that local along with the global, so parent is always
            # global here.
            parent = elements[index]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise TypeError(
                    f"chain parent at index {index} is not global: {parent}"
                )
            child = elements[index + 1]
            parent_def = self._get_chain_element_definition(parent, chain)
            if parent_def is None:
                return validation_diagnostics
            match parent_def:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        chain,
                        child,
                        position_def.constraints,
                        parent.full_typed_name,
                        validation_diagnostics,
                    )
                    index += 1
                case ast.ActionDefinition() as action_def:
                    consumed = self._validate_action_chain_step(
                        chain,
                        child,
                        elements,
                        index + 1,
                        action_def,
                        parent.full_typed_name,
                        validation_diagnostics,
                    )
                    if consumed == 0:
                        return validation_diagnostics
                    index += consumed
                case _:
                    raise TypeError(f"Unexpected definition type: {type(parent_def)}")
        return validation_diagnostics

    def _get_chain_element_definition(
        self,
        parent: ast.GlobalTypedNameReference,
        chain: ast.PositionReference,
    ) -> ast.QualityDefinition | None:
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain error)."""
        parent_result = self._definition_results.get(parent)
        # This means the definition's file did not load or did not parse.
        if parent_result is None:
            self._tracker.mark_error(chain)
            return None
        return parent_result.definition

    def _validate_action_chain_step(
        self,
        chain: ast.PositionReference,
        child: ast.TypedNameReference,
        elements: tuple[ast.TypedNameReference, ...],
        child_index: int,
        action_def: ast.ActionDefinition,
        parent_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> int:
        """Validate chain elements against an action definition's local positions.

        Returns the number of elements consumed (0 means stop walking).
        """
        if not isinstance(child, ast.LocalTypedNameReference):
            self._emit_chain_after_action_diagnostic(
                chain,
                child,
                parent_name,
                diagnostics.ChainGlobalNameAfterActionDiagnostic,
                validation_diagnostics,
            )
            return 0
        if child.full_typed_name not in action_def.interface_positions_by_name:
            self._emit_chain_after_action_diagnostic(
                chain,
                child,
                parent_name,
                diagnostics.ChainElementNotInterfacePositionDiagnostic,
                validation_diagnostics,
            )
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            chain,
            next_child,
            action_def.interface_positions_by_name[child.full_typed_name].constraints,
            child.source_typed_name,
            validation_diagnostics,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraints: ast.PositionConstraintBlock | None,
        parent_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Check that a chain element is an explicit constraint of its parent name."""
        element_name = element.full_typed_name
        declared = constraints.as_set if constraints is not None else frozenset[str]()
        if element_name not in declared:
            validation_diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_error(chain)

    def _emit_chain_after_action_diagnostic(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        parent_name: str,
        diagnostic_class: type[
            diagnostics.ChainGlobalNameAfterActionDiagnostic
            | diagnostics.ChainElementNotInterfacePositionDiagnostic
        ],
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Emit a diagnostic for a chain element that cannot follow an action."""
        validation_diagnostics.append(
            diagnostic_class(
                location=element.location,
                element_name=element.full_typed_name,
                parent_name=parent_name,
            )
        )
        self._tracker.mark_error(chain)
