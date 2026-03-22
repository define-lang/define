"""Post-order occupancy analysis for a single definition."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics
from define.compiler.graphs import action_call_graph
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import dimension_point_tracker

if typing.TYPE_CHECKING:
    from define.compiler.validator import validation_result


class DefinitionOccupancyAnalyzer:
    """Analyzes dimension point occupancy for a single definition's body.

    Runs as part of a DFS post-order walk over the reference graph, after
    all file validation is complete.
    """

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    _diagnostics: list[diagnostics.Diagnostic]
    _action_body_effects: list[action_call_graph.ActionBodyEffect]

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
    ):
        """Initialize with the definition to analyze and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._diagnostics = []
        self._action_body_effects = []

    def analyze(
        self,
    ) -> tuple[list[diagnostics.Diagnostic], list[action_call_graph.ActionBodyEffect]]:
        """Run occupancy analysis and return diagnostics and action body effects."""
        definition = self._definition_result.definition
        if (
            isinstance(definition, ast.ActionDefinition)
            and definition.definition_block is not None
        ):
            self._analyze_action_definition(definition.definition_block)
        elif isinstance(definition, ast.PositionDefinition):
            self._analyze_position_definition(definition)
        return self._diagnostics, self._action_body_effects

    def _analyze_action_definition(self, definition_block: ast.ActionDefinitionBlock):
        definition = self._definition_result.definition
        scope = scope_tracker.ScopeTracker(definition.typed_name.name_content.fqun)
        for local_def in definition_block.interface_positions:
            scope.add_definition(local_def)
        tracker = dimension_point_tracker.LocalDimensionPointTracker(definition)
        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        for condition in definition_block.trigger_conditions.conditions:
            ref = condition.position_reference
            local_ref = tracker.get_local_position_reference(ref, scope)
            if local_ref is not None:
                qualities = scope.get_constraint_names(ref.chain.typed_names[0])
                tracker.create(ref, qualities)
        scope.enter_child_scope()
        self._analyze_statements(definition_block.action_statements, scope, tracker)

    def _analyze_position_definition(self, definition: ast.PositionDefinition):
        if definition.initialization is None:
            return
        scope = scope_tracker.ScopeTracker(definition.typed_name.name_content.fqun)
        scope.add_definition(definition)
        tracker = dimension_point_tracker.LocalDimensionPointTracker(definition)
        self._analyze_statements(definition.initialization, scope, tracker)

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        validity_iter = iter(self._definition_result.dp_statement_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    scope.add_definition(stmt)
                case ast.CreateDimensionPointStatement():
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope, tracker)
                case ast.MoveDimensionPointStatement():
                    validity = next(validity_iter)
                    self._analyze_move(stmt, validity, scope, tracker)

    def _analyze_create(
        self,
        stmt: ast.CreateDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        position = stmt.target_position
        if not validity.target_ok:
            return
        if tracker.has_unknown_state(position):
            return
        local_ref = tracker.get_local_position_reference(position, scope)
        if local_ref is not None:
            if tracker.is_occupied(position):
                existing = tracker.get_occupant(position)
                self._diagnostics.append(
                    diagnostics.CreateInOccupiedPositionDiagnostic(
                        position=position.position,
                        position_name=position.chain.source_chained_name,
                        first_creation_line=existing.creation_position.position.line,
                    )
                )
                return
            qualities = scope.get_constraint_names(position.chain.typed_names[0])
            tracker.create(position, qualities)

        self._action_body_effects.append(
            action_call_graph.ActionBodyEffect(
                enclosing_typed_name=self._definition_result.definition.typed_name,
                statement=stmt,
            )
        )

    def _analyze_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        fqun = self._definition_result.definition.typed_name.name_content.fqun
        if self._check_if_from_is_a_prefix_of_to(stmt, fqun, scope, tracker):
            return
        if not (validity.source_ok and validity.target_ok):
            return
        self._execute_move(stmt, scope, tracker)

    def _execute_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        # First, if either position is in an unknown state, mark both as now having an
        # unknown state and don't do any more checks.
        if tracker.has_unknown_state(stmt.source_position) or tracker.has_unknown_state(
            stmt.target_position
        ):
            tracker.mark_unknown_state(stmt.source_position)
            tracker.mark_unknown_state(stmt.target_position)
            return

        from_local = tracker.get_local_position_reference(stmt.source_position, scope)
        to_local = tracker.get_local_position_reference(stmt.target_position, scope)

        from_occupied = tracker.is_occupied(stmt.source_position)
        to_empty = not tracker.is_occupied(stmt.target_position)

        if not (from_local and to_local):
            # For now, we are assuming that all external positions are fine to
            # move into or from, for the sake of simplicity.
            #
            # TODO: Need to do occupancy tracking on external positions, or more
            # realistically, need to have constraints that enforce that state.
            from_occupied = (not from_local) or from_occupied
            to_empty = (not to_local) or to_empty

        if not from_occupied:
            self._diagnostics.append(
                diagnostics.MoveFromEmptyPositionDiagnostic(
                    position=stmt.source_position.position,
                    position_name=stmt.source_position.chain.source_chained_name,
                )
            )
        if not to_empty:
            occupant = tracker.get_occupant(stmt.target_position)
            occupied_at_line = (
                occupant.creation_position.position.line if occupant else None
            )
            self._diagnostics.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    position=stmt.target_position.position,
                    position_name=stmt.target_position.chain.source_chained_name,
                    occupied_at_line=occupied_at_line,
                )
            )

        if not (from_occupied and to_empty):
            tracker.mark_unknown_state(stmt.source_position)
            tracker.mark_unknown_state(stmt.target_position)
            return

        # Resolve qualities for constraint checking. Local positions use the
        # tracker/scope; chained positions look up the referenced definition.
        fqun = self._definition_result.definition.typed_name.name_content.fqun
        if from_local:
            from_qualities: frozenset[str] | None = tracker.get_occupant(
                stmt.source_position
            ).qualities
        else:
            from_qualities = self._get_required_qualities_for_position(
                stmt.source_position.chain, fqun
            )
        if to_local:
            to_qualities: frozenset[str] | None = scope.get_constraint_names(
                stmt.target_position.chain.typed_names[0]
            )
        else:
            to_qualities = self._get_required_qualities_for_position(
                stmt.target_position.chain, fqun
            )

        if not self._check_move_constraints(
            stmt,
            from_qualities,
            to_qualities,
            both_local=bool(from_local and to_local),
            tracker=tracker,
        ):
            return

        # Update tracker state.
        if from_local and to_local:
            tracker.move(stmt.source_position, stmt.target_position)
        else:
            if from_local:
                tracker.destroy(stmt.source_position)
            elif to_local:
                tracker.create(stmt.target_position, to_qualities or frozenset())

        if not tracker.has_unknown_state(stmt.target_position):
            self._action_body_effects.append(
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=self._definition_result.definition.typed_name,
                    statement=stmt,
                )
            )

    def _check_move_constraints(
        self,
        stmt: ast.MoveDimensionPointStatement,
        from_qualities: frozenset[str] | None,
        to_qualities: frozenset[str] | None,
        *,
        both_local: bool,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ) -> bool:
        """Check that a move satisfies destination constraints.

        Returns True if the move may proceed (constraints satisfied or
        unresolvable). Returns False if constraints are violated and
        both positions are local (marks unknown state).
        """
        if from_qualities is None or to_qualities is None:
            return True
        missing = to_qualities - from_qualities
        if not missing:
            return True

        self._diagnostics.append(
            diagnostics.MoveViolatesConstraintsDiagnostic(
                position=stmt.target_position.chain.typed_names[0].position,
                source_position=stmt.source_position.chain.source_chained_name,
                target_position=stmt.target_position.chain.source_chained_name,
                missing_qualities=sorted(missing),
            )
        )
        if both_local:
            tracker.mark_unknown_state(stmt.source_position)
            tracker.mark_unknown_state(stmt.target_position)
            return False
        return True

    def _check_if_from_is_a_prefix_of_to(
        self,
        stmt: ast.MoveDimensionPointStatement,
        fqun: ast.Fqun,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ) -> bool:
        """Check if the from chain is a prefix of (or identical to) the to chain.

        Returns True if a prefix relationship was detected (and diagnostics emitted).
        """
        from_chain = stmt.source_position.chain
        to_chain = stmt.target_position.chain
        if len(from_chain.typed_names) > len(to_chain.typed_names):
            return False
        for from_name, to_name in zip(
            from_chain.typed_names, to_chain.typed_names, strict=False
        ):
            if from_name.full_typed_name(in_universe=fqun) != to_name.full_typed_name(
                in_universe=fqun
            ):
                return False

        if len(from_chain.typed_names) == len(to_chain.typed_names):
            self._diagnostics.append(
                diagnostics.MoveToSamePositionDiagnostic(
                    position=to_chain.typed_names[-1].position,
                    position_name=to_chain.source_chained_name,
                )
            )
        else:
            divergence = to_chain.typed_names[len(from_chain.typed_names)]
            self._diagnostics.append(
                diagnostics.MoveIntoDefiningPositionDiagnostic(
                    position=divergence.position,
                    source_position=from_chain.source_chained_name,
                    target_position=to_chain.source_chained_name,
                )
            )
            # TODO: Need to export unknown-state positions in FileValidationResult
            # so we know they also can't be checked elsewhere.
            if tracker.get_local_position_reference(stmt.source_position, scope):
                tracker.mark_unknown_state(stmt.source_position)
            if tracker.get_local_position_reference(stmt.target_position, scope):
                tracker.mark_unknown_state(stmt.target_position)
        return True

    def _get_required_qualities_for_position(
        self,
        chain: ast.ChainedName,
        fqun: ast.Fqun,
    ) -> frozenset[str] | None:
        """Resolve the constraint qualities for the last position in a chain."""
        # TODO: This uses the last chain element's constraints as a proxy for what
        # qualities a DP has. A DP may actually have more qualities than the last
        # position requires (from its original creation site), and we lose that
        # knowledge by only looking at its current location.
        last_element = chain.typed_names[-1]

        if isinstance(last_element, ast.GlobalTypedNameReference):
            lookup_key = last_element.full_typed_name(in_universe=fqun)
        else:
            # If the last element is a local reference, then per the
            # guarantees provided by file_validator, it _must_ be
            # a chain with more than one item in it, and the parent
            # must be a globally-named action.
            parent = chain.typed_names[-2]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise ValueError("got a local name where a global name was expected")
            lookup_key = parent.full_typed_name(in_universe=fqun)

        definition_result = self._definition_results.get(lookup_key)
        if definition_result is None:
            return None

        if isinstance(last_element, ast.GlobalTypedNameReference):
            return definition_result.position_constraint_names
        locals_map = definition_result.action_local_position_constraint_names
        return locals_map.get(last_element.name_content.name, frozenset())
