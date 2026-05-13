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
    dimension_point_operation,
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
        return dimension_point_tracker.DimensionPointTracker()

    @cached_property
    def _executor(self) -> dimension_point_operation.DimensionPointOperationExecutor:
        return dimension_point_operation.DimensionPointOperationExecutor(self._tracker)

    @cached_property
    def _implied_quality_list(self) -> list[ast.TypedName]:
        return [
            impl.typed_global_name for impl in self._definition.quality_implications
        ]

    @cached_property
    def _implied_quality_name_set(self) -> frozenset[str]:
        return frozenset(name.full_typed_name for name in self._implied_quality_list)

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
            applied_position_name = requirement.typed_global_name.full_typed_name
            init_block_contract = self._position_contracts.get(applied_position_name)
            if init_block_contract is not None:
                self._tracker.apply_guarantees(
                    position,
                    init_block_contract.guarantees,
                )

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
        action_name = action_ref.full_typed_name
        # The action's file may have failed to load or parse.
        contract = self._action_contracts.get(action_name)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.typed_names[0]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
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
        for req in contract.requirements.values():
            # Example values:
            #   action_chain:
            #     position<box>::action</outer>
            #   req.full_propagation_position_chain():
            #     position<iface>::action</inner>::position<item>
            #   full_caller_chain:
            #     position<box>::action</outer>::position<iface>::action</inner>::position<item>
            full_caller_chain = req.full_propagation_position_chain().in_caller(
                action_chain
            )
            key = full_caller_chain.canonical_chained_name_tuple
            position_name = full_caller_chain.source_form_in_universe(
                self._enclosing_fqun
            )

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
                        position_name=position_name,
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
                        position_name=position_name,
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
                case ast.DestroyDimensionPointStatement():
                    validity = next(validity_iter)
                    self._analyze_destroy(stmt, validity, scope)

    def _analyze_create(
        self,
        stmt: ast.CreateDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        position = stmt.target_position
        if self._tracker.has_unknown_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, position, scope
        )
        if not self._check_parents_occupied(position):
            self._tracker.mark_unknown(position)
            return

        qualities = frozenset(self._get_transitive_required_qualities(position, scope))
        diagnostic = self._executor.execute_create(
            dimension_point_operation.Create(position=position, qualities=qualities)
        )
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            return
        constraints = self._get_constraint_block(position, scope)
        self._apply_position_init_guarantees(position, constraints)
        self._check_trigger(position, scope)

    def _analyze_destroy(
        self,
        stmt: ast.DestroyDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        position = stmt.target_position
        if self._tracker.has_unknown_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, position, scope
        )
        if not self._check_parents_occupied(position):
            self._tracker.mark_unknown(position)
            return

        diagnostic = self._executor.execute_destroy(
            dimension_point_operation.Destroy(position=position)
        )
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            self._tracker.mark_unknown(position)

    def _analyze_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not (validity.source_ok and validity.target_ok):
            return
        if validity.from_is_prefix_of_to:
            self._tracker.mark_unknown(stmt.source_position)
            self._tracker.mark_unknown(stmt.target_position)
            return
        self._validate_chained_name(stmt.source_position, scope)
        self._validate_chained_name(stmt.target_position, scope)
        if (
            stmt.source_position.canonical_chained_name_tuple
            == stmt.target_position.canonical_chained_name_tuple
        ):
            # We can't execute self-to-self moves because it would re-trigger
            # actions if the move is for a trigger position.
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

        move_diagnostics = self._executor.execute_move(
            dimension_point_operation.Move(
                source=from_pos,
                target=to_pos,
                target_required_qualities=self._get_direct_required_qualities(
                    to_pos, scope
                ),
            )
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return
        self._check_trigger(to_pos, scope)

    def _validate_move_preconditions(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Infer chain requirements and check that parent positions are occupied.

        Returns True if both source and target chains have all parents occupied.
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
        return True

    def _validate_chained_name(
        self,
        chain: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Validate chained name elements against their parent name's constraints.

        Marks the chain's occupancy state as UNKNOWN in the tracker if validation fails.
        """
        if len(chain.typed_names) < 2:
            return
        elements = chain.typed_names
        first = elements[0]
        # An interface position (or position-self reference in an init
        # block) at index 0 is in scope and provides its own constraints;
        # every other parent name in the chain must be a global definition
        # that we have to look up.
        index = 0
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                chain,
                elements[1],
                scope.get_constraint_names(first),
                first.full_typed_name,
            )
            index = 1

        while index < len(elements) - 1:
            parent = elements[index]
            child = elements[index + 1]
            parent_def = self._get_chain_element_definition(parent, chain)
            if parent_def is None:
                return
            match parent_def:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        chain,
                        child,
                        position_def.constraint_names,
                        parent.full_typed_name,
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
                    )
                    if consumed == 0:
                        return
                    index += consumed
                case _:
                    raise TypeError(f"Unexpected definition type: {type(parent_def)}")

    def _get_chain_element_definition(
        self,
        parent: ast.TypedNameReference,
        chain: ast.PositionReference,
    ) -> ast.QualityDefinition | None:
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain unknown)."""
        # The file_validator already diagnoses invalid chains before
        # they reach us. However, they still _exist_, so we skip them.
        if not isinstance(parent, ast.GlobalTypedNameReference):
            self._tracker.mark_unknown(chain)
            return None
        parent_result = self._definition_results.get(parent.full_typed_name)
        # This means the definition's file did not load or did not parse.
        if parent_result is None:
            self._tracker.mark_unknown(chain)
            return None
        return parent_result.definition

    def _validate_action_chain_step(
        self,
        chain: ast.PositionReference,
        child: ast.TypedNameReference,
        elements: list[ast.TypedNameReference],
        child_index: int,
        action_def: ast.ActionDefinition,
        parent_name: str,
    ) -> int:
        """Validate chain elements against an action definition's local positions.

        Returns the number of elements consumed (0 means stop walking).
        """
        # TODO: We should emit more specific diagnostics for these cases.
        if not isinstance(child, ast.LocalTypedNameReference):
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        if child.name_type != ast.NameType.POSITION:
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        if child.full_typed_name not in action_def.interface_position_constraints:
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            chain,
            next_child,
            action_def.interface_position_constraints[child.full_typed_name],
            child.source_typed_name,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraint_names: frozenset[str],
        parent_name: str,
    ):
        """Check if a chain element is declared in the parent's constraints (or transitively implied by one)."""
        element_name = element.full_typed_name
        if element_name not in self._expand_constraints_with_implications(
            constraint_names
        ):
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_unknown(chain)

    def _expand_constraints_with_implications(
        self, constraint_names: frozenset[str]
    ) -> frozenset[str]:
        """Return the transitive closure of constraints plus their implications."""
        result: set[str] = set()

        def visit(name: str):
            if name in result:
                return
            result.add(name)
            defn_result = self._definition_results.get(name)
            if defn_result is None:
                return
            defn = defn_result.definition
            for impl in defn.quality_implications:
                visit(impl.typed_global_name.full_typed_name)

        for n in constraint_names:
            visit(n)
        return frozenset(result)

    def _emit_not_in_action_diagnostic(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        parent_name: str,
    ):
        """Emit a diagnostic for a chain element not found in an action definition."""
        self._diagnostics.append(
            diagnostics.ChainElementNotInActionDiagnostic(
                location=element.location,
                element_name=element.full_typed_name,
                parent_name=parent_name,
            )
        )
        self._tracker.mark_unknown(chain)

    # TODO: _get_constraint_block and _get_direct_required_qualities share the same
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
            action_def = self._definition_results[parent.full_typed_name].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return action_def.interface_positions_by_name[
                last_element.full_typed_name
            ].constraints

        definition_result = self._definition_results.get(last_element.full_typed_name)
        if definition_result is None:
            return None
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return position_def.constraints

    def _get_direct_required_qualities(
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
            action_def = self._definition_results[parent.full_typed_name].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return action_def.interface_position_constraints[
                last_element.full_typed_name
            ]

        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(last_element.full_typed_name)
        if definition_result is None:
            return None
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return position_def.constraint_names

    def _get_transitive_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> frozenset[str]:
        direct = self._get_direct_required_qualities(position, scope) or frozenset()
        return self._expand_constraints_with_implications(direct)


class ActionPostorderValidator(DefinitionPostorderValidator):
    """Validates an action definition during a DFS post-order walk."""

    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]

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
        return self._action_definition.interface_positions_by_name

    @property
    def _trigger_position_name(self) -> str | None:
        if self._action_definition.trigger_position is not None:
            return self._action_definition.trigger_position.typed_name.full_typed_name
        return None

    @typing.override
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""
        action_def = self._action_definition
        contract = self._analyze_action_definition(action_def)
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
        if position.typed_names[0].full_typed_name != self._trigger_position_name:
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
        definition: ast.ActionDefinition,
    ) -> action_contract.ActionContract:
        scope = scope_tracker.ScopeTracker()
        for pos in definition.interface_positions:
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
                qualities = frozenset(
                    self._get_transitive_required_qualities(trigger_ref, scope)
                )
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._executor.execute_assume_occupied(
                    dimension_point_operation.AssumeOccupied(
                        position=trigger_ref,
                        qualities=qualities,
                        contracted_position_chain=trigger_ref,
                    )
                )

        scope.enter_child_scope()
        self._analyze_statements(definition.action_statements, scope)

        return self._generate_contract()

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=self._tracker.generate_guarantees(
                self._action_definition.interface_position_names,
                self._implied_quality_list,
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
        """Infer a requirement for a contracted position the first time it is referenced."""
        inferred_from_chain = self._chain_for_inferred_requirement(position, scope)
        if inferred_from_chain is None:
            return

        # The population of the base trigger position itself is handled elsewhere
        # and doesn't create an implicit requirement. (However, actions on children
        # of the position still do create requirements.)
        first_typed_name = position.typed_names[0].full_typed_name
        if (
            scope.is_defined_local(position)
            and self._trigger_position_name == first_typed_name
        ):
            return

        requirement_key = inferred_from_chain.canonical_chained_name_tuple
        if requirement_key in self._inferred_requirements:
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                inferred_from=inferred_from_chain,
                enclosing_action=self._action_definition,
            )
        )

        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            qualities = frozenset(
                self._get_transitive_required_qualities(position, scope)
            )
            self._executor.execute_assume_occupied(
                dimension_point_operation.AssumeOccupied(
                    position=position,
                    qualities=qualities,
                    contracted_position_chain=inferred_from_chain,
                )
            )

    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # It's either an implied position or a self-reference in an init block.
        if position.starts_with_global:
            return position

        first = position.typed_names[0]
        if not scope.is_defined(first):
            return None
        if first.full_typed_name in self._interface_positions:
            return position
        parent_origin = self._parent_comes_from_contracted_position(position)
        if parent_origin is None:
            return None
        # This comes from a contracted position, so we put the requirement on
        # that contracted position, not whatever local position we are inferring
        # a requirement for.
        return position.replace_parent_position_with_prefix(parent_origin)

    def _parent_comes_from_contracted_position(
        self,
        position: ast.ChainedName,
    ) -> ast.PositionReference | None:
        """Return the parent DP's contracted-position origin chain if it came from the caller."""
        parent = position.parent_position()
        if parent is None:
            return None
        parent_key = parent.canonical_chained_name_tuple
        # This check is necessary because we have to run _maybe_infer_reqiuirement
        # before we run _check_parents_occupied, so we can run into situations where
        # the developer has written a statement that operates on the child of a non-existent
        # dimension point. Later, _check_parents_occupied will detect this situation, emit
        # a diagnostic, and mark the relevant position unknown.
        if not self._tracker.is_occupied_by_key(parent_key):
            return None
        dp_info = self._tracker.get_occupant_by_key(parent_key)
        if not dp_info.from_caller:
            return None
        origin_first = dp_info.origin_position.typed_names[0].full_typed_name
        if (
            origin_first not in self._interface_positions
            and origin_first not in self._implied_quality_name_set
        ):
            return None
        return dp_info.origin_position

    def _action_parent_comes_from_contracted_position(
        self,
        trigger_position: ast.PositionReference,
    ) -> tuple[ast.ChainedName, ast.PositionReference | None]:
        """Return the action's parent DP's contracted-position origin chain if it is from the caller."""
        action_chain = trigger_position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError("not an action")
        return (action_chain, self._parent_comes_from_contracted_position(action_chain))

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
        (action_chain, parent_origin) = (
            self._action_parent_comes_from_contracted_position(trigger_position)
        )
        if parent_origin is not None:
            # Triggering an action that is a child of a contracted position.
            caller_path_to_inner_action = (
                action_chain.replace_parent_position_with_prefix(parent_origin)
            )
        elif (
            isinstance(action_chain.typed_names[0], ast.GlobalTypedNameReference)
            and action_chain.typed_names[0].name_type == ast.NameType.ACTION
        ):
            # Triggering an implied action that's not attached to some
            # passed-in dimension point.
            caller_path_to_inner_action = action_chain
        else:
            # Not a contracted position.
            return
        for inner_req in contract.requirements.values():
            full_caller_chain = inner_req.full_propagation_position_chain().in_caller(
                caller_path_to_inner_action
            )
            self._record_propagated_requirement(
                inner_req=inner_req,
                full_caller_chain=full_caller_chain,
                inferred_from=caller_path_to_inner_action,
                propagated_from=inner_req,
                scope=scope,
            )

    def _record_propagated_requirement(
        self,
        *,
        inner_req: action_contract.PositionRequirement,
        full_caller_chain: ast.PositionReference,
        inferred_from: ast.ChainedName,
        propagated_from: action_contract.PositionRequirement | None,
        scope: scope_tracker.ScopeTracker,
    ):
        """Record a requirement propagated from a triggered action's contract."""
        propagated_key = full_caller_chain.canonical_chained_name_tuple
        # If we already inferred a requirement for this key (i.e.,
        # our own code references this position first), we satisfy
        # the requirement ourselves and thus don't propagate it to our caller.
        if propagated_key in self._inferred_requirements:
            return
        self._inferred_requirements[propagated_key] = (
            action_contract.PositionRequirement(
                required_state=inner_req.required_state,
                inferred_from=inferred_from,
                enclosing_action=self._action_definition,
                propagated_from=propagated_from,
            )
        )
        if inner_req.required_state == action_contract.PositionOccupancyState.OCCUPIED:
            # The triggered action's OccupiedByExisting guarantees can carry
            # this synthesized DP into other positions that later statements
            # reference, so its qualities must match what a real
            # caller-supplied DP would carry transitively via Quality
            # Requirement Statements.
            qualities = frozenset(
                self._get_transitive_required_qualities(full_caller_chain, scope)
            )
            self._executor.execute_assume_occupied(
                dimension_point_operation.AssumeOccupied(
                    position=full_caller_chain,
                    qualities=qualities,
                    contracted_position_chain=full_caller_chain,
                )
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
        scope = scope_tracker.ScopeTracker()
        scope.add_definition(definition)
        self._analyze_statements(definition.initialization, scope)
        return action_contract.PositionInitBlockContract(
            guarantees=self._tracker.generate_guarantees(
                [definition.typed_name],
                self._implied_quality_list,
            ),
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
