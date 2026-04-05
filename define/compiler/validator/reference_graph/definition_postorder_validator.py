"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import ast, diagnostics
from define.compiler.graphs import action_call_graph
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    dimension_point_tracker,
)

if typing.TYPE_CHECKING:
    from define.compiler.validator import validation_result


@dataclass
class PostorderValidationResult:
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)
    edges: list[action_call_graph.ActionGraphEdge] = field(default_factory=list)
    contract: action_contract.ActionStatementsBlockContract | None = None


class DefinitionPostorderValidator(abc.ABC):
    """Validates a single definition during a DFS post-order walk of the reference graph."""

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    _action_contracts: dict[str, action_contract.ActionContract]
    _position_contracts: dict[str, action_contract.PositionInitBlockContract]
    _diagnostics: list[diagnostics.Diagnostic]
    _action_edges: list[action_call_graph.ActionGraphEdge]

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
        action_contracts: dict[str, action_contract.ActionContract],
        position_contracts: dict[str, action_contract.PositionInitBlockContract],
    ):
        """Initialize with the definition to validate and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._action_contracts = action_contracts
        self._position_contracts = position_contracts
        self._diagnostics = []
        self._action_edges = []

    @property
    def _definition(self) -> ast.QualityDefinition:
        return self._definition_result.definition

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> dimension_point_tracker.DimensionPointTracker:
        return dimension_point_tracker.DimensionPointTracker(self._definition)

    @abc.abstractmethod
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""

    def _maybe_infer_requirement(  # noqa: B027
        self,
        required_state: action_contract.PositionOccupancyState,  # pyright: ignore[reportUnusedParameter]
        position: ast.PositionReference,  # pyright: ignore[reportUnusedParameter]
        scope: scope_tracker.ScopeTracker,  # pyright: ignore[reportUnusedParameter]
    ):
        """Infer a requirement for an interface position on first reference.

        No-op for non-action definitions. Overridden by ActionPostorderValidator.
        """

    def _propagate_inner_requirements(  # noqa: B027
        self,
        _triggered_action: ast.GlobalTypedNameReference,
        _triggered_action_name: str,
        _contract: action_contract.ActionContract,
        _trigger_position: ast.PositionReference,
        _scope: scope_tracker.ScopeTracker,
    ):
        """Propagate inner action requirements into this action's contract.

        No-op for non-action definitions. Overridden by ActionPostorderValidator.
        """

    def _maybe_infer_requirements_on_chain(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer requirements for a position and all its parent positions.

        The leaf position uses the given required_state; all parent positions
        use OCCUPIED, since a parent must be occupied for its child to be
        accessible. Walks root-to-leaf so the tracker trie has parent nodes
        in place when children are inserted.
        """
        for parent in position.walk_parent_positions():
            self._maybe_infer_requirement(
                action_contract.PositionOccupancyState.OCCUPIED, parent, scope
            )
        self._maybe_infer_requirement(required_state, position, scope)

    def _check_parents_occupied(
        self,
        position: ast.PositionReference,
    ) -> bool:
        """Check that all parent positions contain dimension points.

        Walks leaf-to-root. Emits a separate diagnostic for each unoccupied
        parent.

        Does NOT mark the position unknown — the caller handles that.
        """
        ok = True
        current = position.parent_position()
        while current is not None:
            if self._tracker.has_unknown_state(current):
                current = current.parent_position()
                continue
            if self._tracker.is_occupied(current):
                break
            self._diagnostics.append(
                diagnostics.ParentPositionNotOccupiedDiagnostic(
                    location=position.location,
                    position_name=position.source_chained_name,
                    parent_position_name=current.source_chained_name,
                )
            )
            ok = False
            current = current.parent_position()
        return ok

    def _apply_position_init_guarantees(
        self,
        position: ast.PositionReference,
        constraints: ast.PositionConstraintBlock | None,
    ):
        """Apply position init block guarantees for each assigned quality in source order."""
        if constraints is None:
            return
        for requirement in constraints.requirements:
            if requirement.typed_global_name.name_type != ast.NameType.POSITION:
                continue
            applied_position_name = requirement.typed_global_name.full_typed_name(
                in_universe=self._enclosing_fqun
            )
            init_block_contract = self._position_contracts.get(applied_position_name)
            if init_block_contract is not None:
                self._tracker.apply_guarantees(position, init_block_contract.guarantees)

    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check if filling this interface position triggers the named action.

        Only triggers when the chain ends with action<...>::position<trigger>,
        i.e., we're directly filling an action's interface position.
        """
        interface_position = position.get_last_action_children()
        if interface_position is None:
            return
        # Only trigger when filling a single interface position directly,
        # not children of interface positions.
        if len(interface_position.typed_names) != 1:
            return
        # Never None, because interface_position is not None.
        action_ref = typing.cast(
            "ast.GlobalTypedNameReference", position.get_last_action()
        )
        action_name = action_ref.full_typed_name(in_universe=self._enclosing_fqun)
        # The action's file may have failed to load or parse.
        contract = self._action_contracts.get(action_name)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.typed_names[0]
        )
        if (
            trigger_element.full_typed_name(in_universe=self._enclosing_fqun)
            != contract.trigger_position_name
        ):
            return

        # We only propagate inner requirements if actions actually get called.
        # (That's why this happens here in _check_trigger.)
        self._propagate_inner_requirements(
            action_ref, action_name, contract, position, scope
        )
        self._check_requirements(position, contract)
        self._tracker.apply_guarantees(position, contract.guarantees)
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action_name,
            )
        )

    def _check_requirements(
        self,
        trigger_position: ast.PositionReference,
        contract: action_contract.ActionContract,
    ):
        """Check that all action requirements are satisfied before triggering."""
        dp = self._tracker.get_occupant(trigger_position)

        action_chain = trigger_position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError(
                f"no action in chain: {trigger_position.source_chained_name}"
            )
        # source_prefix is for diagnostics, canonical_prefix is for key lookups.
        source_prefix = action_chain.source_chained_name
        canonical_prefix = action_chain.canonical_chained_name_tuple(
            in_universe=self._enclosing_fqun
        )

        for req_key, req in contract.requirements.items():
            key = canonical_prefix + req_key

            if self._tracker.has_unknown_state_by_key(key):
                continue

            is_occupied = self._tracker.is_occupied_by_key(key)

            if (
                req.required_state == action_contract.PositionOccupancyState.EMPTY
                and is_occupied
            ):
                occupant = self._tracker.get_occupant_by_key(key)
                self._diagnostics.append(
                    diagnostics.ActionRequiresEmptyPositionDiagnostic(
                        location=dp.last_position.location,
                        action_name=req.root_cause_action_name(),
                        position_name=f"{source_prefix}::{req.resolved_chained_name(self._enclosing_fqun)}",
                        inferred_at=req.inferred_from.location,
                        propagated_from_locations=req.propagated_from_locations(),
                        filled_at=occupant.last_position.location,
                    )
                )
            elif (
                req.required_state == action_contract.PositionOccupancyState.OCCUPIED
                and not is_occupied
            ):
                self._diagnostics.append(
                    diagnostics.ActionRequiresOccupiedPositionDiagnostic(
                        location=dp.last_position.location,
                        action_name=req.root_cause_action_name(),
                        position_name=f"{source_prefix}::{req.resolved_chained_name(self._enclosing_fqun)}",
                        inferred_at=req.inferred_from.location,
                        propagated_from_locations=req.propagated_from_locations(),
                    )
                )

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        validity_iter = iter(self._definition_result.dp_statement_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    scope.add_definition(stmt)
                case ast.CreateDimensionPointStatement():
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope)
                case ast.MoveDimensionPointStatement():
                    validity = next(validity_iter)
                    self._analyze_move(stmt, validity, scope)

    def _analyze_create(
        self,
        stmt: ast.CreateDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_chained_name(stmt.target_position, scope)
        position = stmt.target_position
        if not validity.target_ok:
            return
        if self._tracker.has_unknown_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, position, scope
        )
        if not self._check_parents_occupied(position):
            self._tracker.mark_unknown(position)
            return
        if self._tracker.is_occupied(position):
            self._diagnostics.append(
                diagnostics.CreateInOccupiedPositionDiagnostic(
                    location=position.location,
                    position_name=position.source_chained_name,
                    created_at=self._tracker.get_occupant(
                        position
                    ).last_position.location,
                )
            )
            return

        qualities = self._get_required_qualities(position, scope) or frozenset()
        self._tracker.create(position, qualities)
        self._apply_position_init_guarantees(
            position, self._get_constraint_block(position, scope)
        )
        self._check_trigger(position, scope)

    def _analyze_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_chained_name(stmt.source_position, scope)
        self._validate_chained_name(stmt.target_position, scope)
        if self._check_if_from_is_a_prefix_of_to(stmt):
            return
        if not (validity.source_ok and validity.target_ok):
            return
        self._execute_move(stmt.source_position, stmt.target_position, scope)

    def _execute_move(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Execute a move and update tracker state."""
        if self._tracker.has_unknown_state(from_pos) or self._tracker.has_unknown_state(
            to_pos
        ):
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return

        if not self._validate_move_preconditions(from_pos, to_pos, scope):
            return

        self._tracker.move(from_pos, to_pos)
        self._check_trigger(to_pos, scope)

    def _validate_move_preconditions(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Validate occupancy, infer requirements, and check constraints.

        Returns True if the move may proceed.
        """
        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, to_pos, scope
        )

        from_parent_ok = self._check_parents_occupied(from_pos)
        to_parent_ok = self._check_parents_occupied(to_pos)
        if not (from_parent_ok and to_parent_ok):
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return False

        from_action = from_pos.get_last_action()
        from_occupied = self._tracker.is_occupied(from_pos)
        to_empty = not self._tracker.is_occupied(to_pos)

        if not from_occupied:
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(from_pos)
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
                        location=from_pos.location,
                        position_name=from_pos.source_chained_name,
                        inferred_at=emptied_by.location if emptied_by else None,
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyPositionDiagnostic(
                        location=from_pos.location,
                        position_name=from_pos.source_chained_name,
                    )
                )
        if not to_empty:
            occupant = self._tracker.get_occupant(to_pos)
            self._diagnostics.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    location=to_pos.location,
                    position_name=to_pos.source_chained_name,
                    occupied_at=occupant.last_position.location,
                )
            )

        if not (from_occupied and to_empty):
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return False

        from_qualities = self._tracker.get_occupant(from_pos).qualities
        to_qualities = self._get_required_qualities(to_pos, scope)

        return self._check_move_constraints(
            from_pos, to_pos, from_qualities, to_qualities
        )

    def _check_move_constraints(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        from_qualities: frozenset[str] | None,
        to_qualities: frozenset[str] | None,
    ) -> bool:
        """Check that a move satisfies destination constraints.

        Returns True if the move may proceed. Returns False if constraints are
        violated (marks unknown state).
        """
        if from_qualities is None or to_qualities is None:
            return True
        missing = to_qualities - from_qualities
        if not missing:
            return True

        self._diagnostics.append(
            diagnostics.MoveViolatesConstraintsDiagnostic(
                location=to_pos.typed_names[0].location,
                source_position=from_pos.source_chained_name,
                target_position=to_pos.source_chained_name,
                missing_qualities=sorted(missing),
            )
        )
        self._tracker.mark_unknown(from_pos)
        self._tracker.mark_unknown(to_pos)
        return False

    def _check_if_from_is_a_prefix_of_to(
        self,
        stmt: ast.MoveDimensionPointStatement,
    ) -> bool:
        """Check if the from chain is a prefix of (or identical to) the to chain.

        Returns True if a prefix relationship was detected (and diagnostics emitted).
        """
        fqun = self._enclosing_fqun
        from_pos = stmt.source_position
        to_pos = stmt.target_position
        if len(from_pos.typed_names) > len(to_pos.typed_names):
            return False
        for from_name, to_name in zip(
            from_pos.typed_names, to_pos.typed_names, strict=False
        ):
            if from_name.full_typed_name(in_universe=fqun) != to_name.full_typed_name(
                in_universe=fqun
            ):
                return False

        if len(from_pos.typed_names) == len(to_pos.typed_names):
            self._diagnostics.append(
                diagnostics.MoveToSamePositionDiagnostic(
                    location=to_pos.typed_names[-1].location,
                    position_name=to_pos.source_chained_name,
                )
            )
        else:
            divergence = to_pos.typed_names[len(from_pos.typed_names)]
            self._diagnostics.append(
                diagnostics.MoveIntoDefiningPositionDiagnostic(
                    location=divergence.location,
                    source_position=from_pos.source_chained_name,
                    target_position=to_pos.source_chained_name,
                )
            )
            self._tracker.mark_unknown(stmt.source_position)
            self._tracker.mark_unknown(stmt.target_position)
        return True

    def _validate_chained_name(
        self,
        ref: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Validate chained name elements against their parent name's constraints.

        Marks the chain's position as UNKNOWN in the tracker if validation fails.
        """
        if len(ref.typed_names) < 2:
            return
        enclosing_fqun = self._enclosing_fqun
        elements = ref.typed_names

        # Check the second element against the first element's constraints
        # using the scope tracker. This works also for position-self references
        # because we inserted the position's definition into the scope already.
        first = elements[0]
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                ref,
                elements[1],
                scope.get_constraint_names(first),
                first.full_typed_name(in_universe=enclosing_fqun),
                enclosing_fqun,
            )

        index = 1
        while index < len(elements) - 1:
            parent = elements[index]
            # The file_validator already diagnoses invalid chains before
            # they reach us. However, they still _exist_, so we skip them.
            if not isinstance(parent, ast.GlobalTypedNameReference):
                self._tracker.mark_unknown(ref)
                return
            parent_name = parent.full_typed_name(in_universe=enclosing_fqun)
            parent_result = self._definition_results.get(parent_name)
            # This means the definition's file did not load or did not parse.
            if parent_result is None:
                self._tracker.mark_unknown(ref)
                return
            child = elements[index + 1]
            match parent_result.definition:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        ref,
                        child,
                        position_def.constraint_names,
                        parent_name,
                        enclosing_fqun,
                    )
                    index += 1
                case ast.ActionDefinition() as action_def:
                    consumed = self._validate_action_chain_step(
                        ref,
                        child,
                        elements,
                        index + 1,
                        action_def,
                        parent_name,
                        enclosing_fqun,
                    )
                    if consumed == 0:
                        return
                    index += consumed
                case _:
                    raise TypeError(
                        f"Unexpected definition type: {type(parent_result.definition)}"
                    )

    def _validate_action_chain_step(
        self,
        ref: ast.PositionReference,
        child: ast.TypedNameReference,
        elements: list[ast.TypedNameReference],
        child_index: int,
        action_def: ast.ActionDefinition,
        parent_name: str,
        fqun: ast.Fqun,
    ) -> int:
        """Validate chain elements against an action definition's local positions.

        Returns the number of elements consumed (0 means stop walking).
        """
        # TODO: We should emit more specific diagnostics for these cases.
        if not isinstance(child, ast.LocalTypedNameReference):
            self._emit_not_in_action_diagnostic(ref, child, parent_name, fqun)
            return 0
        if child.name_type != ast.NameType.POSITION:
            self._emit_not_in_action_diagnostic(ref, child, parent_name, fqun)
            return 0
        if (
            child.full_typed_name(in_universe=fqun)
            not in action_def.interface_position_constraints
        ):
            self._emit_not_in_action_diagnostic(ref, child, parent_name, fqun)
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            ref,
            next_child,
            action_def.interface_position_constraints[
                child.full_typed_name(in_universe=fqun)
            ],
            child.source_typed_name,
            fqun,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        ref: ast.PositionReference,
        element: ast.TypedNameReference,
        constraint_names: frozenset[str],
        parent_name: str,
        fqun: ast.Fqun,
    ):
        """Check if a chain element is declared in the parent's constraints."""
        element_name = element.full_typed_name(in_universe=fqun)
        if element_name not in constraint_names:
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_unknown(ref)

    def _emit_not_in_action_diagnostic(
        self,
        ref: ast.PositionReference,
        element: ast.TypedNameReference,
        parent_name: str,
        fqun: ast.Fqun,
    ):
        """Emit a diagnostic for a chain element not found in an action definition."""
        self._diagnostics.append(
            diagnostics.ChainElementNotInActionDiagnostic(
                location=element.location,
                element_name=element.full_typed_name(in_universe=fqun),
                parent_name=parent_name,
            )
        )
        self._tracker.mark_unknown(ref)

    # TODO: _get_constraint_block and _get_required_qualities share the same
    # position-resolution logic and should be refactored to use a common helper.
    def _get_constraint_block(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> ast.PositionConstraintBlock | None:
        """Resolve the constraint block for the position definition."""
        if scope.is_defined_local(position):
            return scope.get_definition(position.typed_names[0]).constraints

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            parent = position.typed_names[-2]
            parent_key = parent.full_typed_name(in_universe=self._enclosing_fqun)
            action_def = self._definition_results[parent_key].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            local_pos_name = last_element.full_typed_name(
                in_universe=self._enclosing_fqun
            )
            return action_def.interface_positions[local_pos_name].constraints

        lookup_key = last_element.full_typed_name(in_universe=self._enclosing_fqun)
        definition_result = self._definition_results.get(lookup_key)
        if definition_result is None:
            return None
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return position_def.constraints

    def _get_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> frozenset[str] | None:
        """Resolve the constraint qualities required at a position."""
        if scope.is_defined_local(position):
            return scope.get_constraint_names(position.typed_names[0])

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface_position_constraints. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position.
            parent = position.typed_names[-2]
            parent_key = parent.full_typed_name(in_universe=self._enclosing_fqun)
            action_def = self._definition_results[parent_key].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return action_def.interface_position_constraints[
                last_element.full_typed_name(in_universe=self._enclosing_fqun)
            ]

        lookup_key = last_element.full_typed_name(in_universe=self._enclosing_fqun)
        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(lookup_key)
        if definition_result is None:
            return None
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return position_def.constraint_names


class ActionPostorderValidator(DefinitionPostorderValidator):
    """Validates an action definition during a DFS post-order walk."""

    _inferred_requirements: dict[
        tuple[str, ...], action_contract.InterfacePositionRequirement
    ]

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
        action_contracts: dict[str, action_contract.ActionContract],
        position_contracts: dict[str, action_contract.PositionInitBlockContract],
    ):
        """Initialize with the action definition to validate and the full results map."""
        super().__init__(
            definition_result,
            definition_results,
            action_contracts,
            position_contracts,
        )
        self._inferred_requirements = {}

    @property
    def _action_definition(self) -> ast.ActionDefinition:
        return typing.cast("ast.ActionDefinition", self._definition)

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._action_definition.interface_positions

    @property
    def _trigger_position_name(self) -> str | None:
        if self._action_definition.trigger_position is not None:
            return self._action_definition.trigger_position.typed_name.full_typed_name(
                in_universe=self._enclosing_fqun
            )
        return None

    @typing.override
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""
        action_def = self._action_definition
        contract = self._analyze_action_definition(action_def.definition_block)
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
        )

    @typing.override
    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        if position.get_last_action_children() is not None:
            super()._check_trigger(position, scope)
            return
        if self._trigger_position_name is None:
            return
        if len(position.typed_names) != 1:
            return
        pos_name = position.typed_names[0].full_typed_name(
            in_universe=self._enclosing_fqun
        )
        if pos_name != self._trigger_position_name:
            return
        self._diagnostics.append(
            diagnostics.ActionSelfTriggerDiagnostic(
                location=position.location,
                action_name=self._definition.typed_name.source_typed_name,
                position_name=position.source_chained_name,
            )
        )

    def _analyze_action_definition(
        self,
        definition_block: ast.ActionDefinitionBlock,
    ) -> action_contract.ActionContract:
        scope = scope_tracker.ScopeTracker(self._enclosing_fqun)
        for pos in definition_block.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._action_definition.trigger_position_reference
        if trigger_ref is not None:
            typed_name = trigger_ref.typed_names[0]
            if scope.is_defined(typed_name):
                qualities = scope.get_constraint_names(typed_name)
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._tracker.create(trigger_ref, qualities, from_caller=True)

        scope.enter_child_scope()
        self._analyze_statements(definition_block.action_statements, scope)

        return self._generate_contract()

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=self._tracker.generate_guarantees(
                self._action_definition.interface_position_names
            ),
            trigger_position_name=self._trigger_position_name or "",
        )

    @typing.override
    def _maybe_infer_requirement(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for an interface position the first time it is referenced."""
        first = position.typed_names[0]
        if not scope.is_defined(first):
            return
        first_typed_name = first.full_typed_name(in_universe=self._enclosing_fqun)
        first_is_interface = first_typed_name in self._interface_positions
        inferred_from_chain = position
        if not first_is_interface:
            parent_interface_position = self._parent_comes_from_interface_position(
                position
            )
            if parent_interface_position is None:
                return
            # When the parent came from the caller (via a moved interface
            # position), remap the requirement through the original interface
            # position so the requirement key and diagnostic match the caller's
            # view of the world.
            inferred_from_chain: ast.ChainedName = (
                self._remap_through_interface_position(
                    position, parent_interface_position
                )
            )

        # The population of the base trigger position itself is handled elsewhere
        # and doesn't create an implicit requirement. (However, actions on children
        # of the position still do create requirements.)
        if (
            scope.is_defined_local(position)
            and self._trigger_position_name == first_typed_name
        ):
            return

        requirement_key = inferred_from_chain.canonical_chained_name_tuple(
            in_universe=self._enclosing_fqun
        )
        if requirement_key in self._inferred_requirements:
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.InterfacePositionRequirement(
                required_state=required_state,
                inferred_from=inferred_from_chain,
                enclosing_action=self._action_definition,
            )
        )

        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            qualities = self._get_required_qualities(position, scope) or frozenset()
            self._tracker.create(position, qualities, from_caller=True)

    def _parent_comes_from_interface_position(
        self,
        position: ast.ChainedName,
    ) -> ast.LocalPositionDefinition | None:
        """Return the interface position if the parent DP came from the caller."""
        parent = position.parent_position()
        if parent is None:
            return None
        parent_key = parent.canonical_chained_name_tuple(
            in_universe=self._enclosing_fqun
        )
        # This check is necessary because we have to run _maybe_infer_reqiuirement
        # before we run _check_parents_occupied, so we can run into situations where
        # the developer has written a statement that operates on the child of a non-existent
        # dimension point. Later, _chck_parents_occupied will detect this situation, emit
        # a diagnostic, and mark the relevant position unknown.
        if not self._tracker.is_occupied_by_key(parent_key):
            return None
        dp_info = self._tracker.get_occupant_by_key(parent_key)
        if not dp_info.from_caller:
            return None
        origin_first = dp_info.origin_position.typed_names[0]
        origin_key = origin_first.full_typed_name(in_universe=self._enclosing_fqun)
        return self._interface_positions.get(origin_key)

    def _remap_through_interface_position(
        self,
        chain: ast.ChainedName,
        iface_def: ast.LocalPositionDefinition,
    ) -> ast.ChainedName:
        """Replace a chain's parent prefix with the original interface position."""
        parent = chain.parent_position()
        if parent is None:
            raise ValueError(
                f"cannot remap single-element chain: {chain.source_chained_name}"
            )
        return ast.ChainedName(
            location=chain.location,
            typed_names=[
                iface_def.typed_name,
                *chain.typed_names[len(parent.typed_names) :],
            ],
        )

    def _action_parent_comes_from_interface_position(
        self,
        trigger_position: ast.PositionReference,
    ) -> tuple[ast.ChainedName, ast.LocalPositionDefinition | None]:
        """Return the interface position definition if the action's parent DP is from the caller.

        Only the action's immediate parent position matters. If the parent
        DP is from_caller, the caller injected it, so the caller has access
        to the rest of the chain and could have pre-filled the action's interface
        positions. Thus, requirements must propagate. If the parent DP is NOT
        from_caller (created internally by this action), the caller's access
        was severed, so requirements don't propagate.
        """
        action_chain = trigger_position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError("not an action")
        return (action_chain, self._parent_comes_from_interface_position(action_chain))

    @typing.override
    def _propagate_inner_requirements(
        self,
        triggered_action: ast.GlobalTypedNameReference,
        triggered_action_name: str,
        contract: action_contract.ActionContract,
        trigger_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate inner action requirements into this action's contract."""
        (action_chain, iface_def) = self._action_parent_comes_from_interface_position(
            trigger_position
        )
        if iface_def is None:
            return

        # The caller sees only the interface position and the action, not any
        # internal positions the DP may have been moved through. (That's why
        # we only append action_chain to the interface position.)
        remapped_prefix = self._remap_through_interface_position(
            action_chain, iface_def
        )
        canonical_key_prefix = remapped_prefix.canonical_chained_name_tuple(
            in_universe=self._enclosing_fqun
        )
        for req_key, inner_req in contract.requirements.items():
            propagated_key = (*canonical_key_prefix, *req_key)
            # If we already inferred a requirement for this key (i.e.,
            # our own code references this position first), we satisfy
            # it ourselves and don't propagate it to our caller.
            if propagated_key in self._inferred_requirements:
                continue
            self._inferred_requirements[propagated_key] = (
                action_contract.InterfacePositionRequirement(
                    required_state=inner_req.required_state,
                    inferred_from=remapped_prefix,
                    enclosing_action=self._action_definition,
                    propagated_from=inner_req,
                )
            )
            if (
                inner_req.required_state
                == action_contract.PositionOccupancyState.OCCUPIED
            ):
                propagated_position = ast.PositionReference(
                    location=remapped_prefix.location,
                    typed_names=remapped_prefix.typed_names
                    + inner_req.propagation_chain_typed_names(),
                )
                qualities = (
                    self._get_required_qualities(propagated_position, scope)
                    or frozenset()
                )
                self._tracker.create_by_key(
                    propagated_key,
                    propagated_position,
                    qualities,
                    from_caller=True,
                )


class PositionPostorderValidator(DefinitionPostorderValidator):
    """Validates a position definition during a DFS post-order walk."""

    @typing.override
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics and edges."""
        definition = self._definition
        if not isinstance(definition, ast.PositionDefinition):
            raise TypeError(f"Expected PositionDefinition, got {type(definition)}")
        contract = self._analyze_position_definition(definition)
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
        )

    def _analyze_position_definition(
        self, definition: ast.PositionDefinition
    ) -> action_contract.PositionInitBlockContract | None:
        if definition.initialization is None:
            return None
        scope = scope_tracker.ScopeTracker(definition.typed_name.name_content.fqun)
        scope.add_definition(definition)
        self._analyze_statements(definition.initialization, scope)
        return action_contract.PositionInitBlockContract(
            guarantees=self._tracker.generate_guarantees([definition.typed_name]),
        )


def create_postorder_validator(
    definition_result: validation_result.DefinitionValidationResult,
    definition_results: dict[str, validation_result.DefinitionValidationResult],
    action_contracts: dict[str, action_contract.ActionContract],
    position_contracts: dict[str, action_contract.PositionInitBlockContract],
) -> DefinitionPostorderValidator:
    """Create the appropriate postorder validator for the given definition."""
    if isinstance(definition_result.definition, ast.ActionDefinition):
        return ActionPostorderValidator(
            definition_result,
            definition_results,
            action_contracts,
            position_contracts,
        )
    if isinstance(definition_result.definition, ast.PositionDefinition):
        return PositionPostorderValidator(
            definition_result,
            definition_results,
            action_contracts,
            position_contracts,
        )
    raise TypeError(f"Unexpected definition type: {type(definition_result.definition)}")
