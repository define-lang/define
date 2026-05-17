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
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]

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
        self._inferred_requirements = {}

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
    def _implied_quality_list(self) -> list[ast.GlobalTypedNameReference]:
        return [
            impl.typed_global_name for impl in self._definition.quality_implications
        ]

    @abc.abstractmethod
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""

    def _maybe_infer_requirement(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for a contracted position the first time it is referenced."""
        inferred_from_chain = self._chain_for_inferred_requirement(position)
        if inferred_from_chain is None:
            return

        requirement_key = inferred_from_chain.canonical_chained_name_tuple
        if requirement_key in self._inferred_requirements:
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                inferred_from=inferred_from_chain,
                enclosing_quality=self._definition,
            )
        )

        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            qualities = self._get_transitive_required_qualities(position, scope)
            self._executor.execute_assume_occupied(
                dimension_point_operation.AssumeOccupied(
                    target=position,
                    qualities=qualities,
                    contracted_position_chain=inferred_from_chain,
                )
            )

    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
    ) -> ast.PositionReference | None:
        """Return the chain to record as ``inferred_from``, or None if this isn't a contracted position."""
        # Implied quality.
        if position.starts_with_global:
            return position
        parent_origin = self._parent_dimension_point_comes_from_caller(position)
        if parent_origin is None:
            return None
        # This comes from a contracted position, so we put the requirement on
        # that contracted position, not whatever local position we are inferring
        # a requirement for.
        return position.replace_parent_position_with_prefix(parent_origin)

    def _propagate_inner_requirements(
        self,
        contract: action_contract.ActionContract,
        trigger_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the triggered action's requirements into this definition's contract."""
        (action_chain, parent_origin) = (
            self._action_parent_comes_from_contracted_position(trigger_position)
        )
        if parent_origin is not None:
            caller_path_to_inner_action = (
                action_chain.replace_parent_position_with_prefix(parent_origin)
            )
        elif (
            isinstance(action_chain.typed_names[0], ast.GlobalTypedNameReference)
            and action_chain.typed_names[0].name_type == ast.NameType.ACTION
        ):
            caller_path_to_inner_action = action_chain
        else:
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

    def _parent_dimension_point_comes_from_caller(
        self,
        position: ast.ChainedName,
    ) -> ast.PositionReference | None:
        """Return the parent DP's contracted-position origin chain if it came from the caller."""
        parent = position.parent_position()
        if parent is None:
            return None
        parent_key = parent.canonical_chained_name_tuple
        # This check is necessary because we have to run _maybe_infer_requirement
        # before the executor runs its parent-occupancy check, so we can run into
        # situations where the developer has written a statement that operates on
        # the child of a non-existent dimension point. The executor's parent check
        # will later detect this situation, emit a diagnostic, and mark the
        # relevant position unknown.
        if not self._tracker.is_occupied_by_key(parent_key):
            return None
        dp_info = self._tracker.get_occupant_by_key(parent_key)
        if not dp_info.from_caller:
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
        return (
            action_chain,
            self._parent_dimension_point_comes_from_caller(action_chain),
        )

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

    def _run_position_init_blocks(
        self,
        position: ast.PositionReference,
        qualities: list[ast.GlobalTypedNameReference],
        scope: scope_tracker.ScopeTracker,
    ):
        """Run the caller-side effects of every implied position's init block."""
        for quality in qualities:
            if quality.name_type != ast.NameType.POSITION:
                continue
            init_block_contract = self._position_contracts.get(quality.full_typed_name)
            if init_block_contract is None:
                continue
            self._propagate_init_block_requirements(
                position, init_block_contract, scope
            )
            self._check_init_block_requirements(position, init_block_contract)
            self._tracker.apply_guarantees(
                position,
                init_block_contract.guarantees,
            )

    def _propagate_init_block_requirements(
        self,
        create_target: ast.PositionReference,
        init_block_contract: action_contract.PositionInitBlockContract,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the init block's requirements into the enclosing definition's contract."""
        caller_path = self._chain_for_inferred_requirement(create_target)
        if caller_path is None:
            return
        for inner_req in init_block_contract.requirements.values():
            full_caller_chain = inner_req.full_propagation_position_chain().in_caller(
                caller_path
            )
            self._record_propagated_requirement(
                inner_req=inner_req,
                full_caller_chain=full_caller_chain,
                inferred_from=caller_path,
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
        """Record a requirement propagated from an inner contract."""
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
                enclosing_quality=self._definition,
                propagated_from=propagated_from,
            )
        )
        if inner_req.required_state == action_contract.PositionOccupancyState.OCCUPIED:
            # We can't know exactly what qualities the dimension point has, but we
            # can know the minimal set that it _must_ have according to the constraints
            # the position has.
            qualities = self._get_transitive_required_qualities(
                full_caller_chain, scope
            )
            self._executor.execute_assume_occupied(
                dimension_point_operation.AssumeOccupied(
                    target=full_caller_chain,
                    qualities=qualities,
                    contracted_position_chain=full_caller_chain,
                )
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
        self._propagate_inner_requirements(contract, position, scope)
        self._check_action_requirements(position, contract)
        self._tracker.apply_guarantees(position, contract.guarantees)
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action_name,
            )
        )

    def _check_action_requirements(
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
            #   full_caller_chain (composed via in_caller):
            #     position<box>::action</outer>::position<iface>::action</inner>::position<item>
            full_caller_chain = req.full_propagation_position_chain().in_caller(
                action_chain
            )
            self._check_one_requirement(full_caller_chain, dp.last_position, req)

    def _check_init_block_requirements(
        self,
        create_target: ast.PositionReference,
        contract: action_contract.PositionInitBlockContract,
    ):
        """Check that all init-block requirements hold at the Create statement that assigns the position."""
        for req in contract.requirements.values():
            # Example values:
            #   create_target:
            #     position<box>
            #   req.full_propagation_position_chain():
            #     position</q>::position</q_child>
            #   full_caller_chain (composed via in_caller):
            #     position<box>::position</q>::position</q_child>
            full_caller_chain = req.full_propagation_position_chain().in_caller(
                create_target
            )
            self._check_one_requirement(full_caller_chain, create_target, req)

    def _check_one_requirement(
        self,
        full_caller_chain: ast.PositionReference,
        caller_position: ast.PositionReference,
        req: action_contract.PositionRequirement,
    ):
        """Emit a diagnostic if a single requirement is not satisfied."""
        key = full_caller_chain.canonical_chained_name_tuple
        position_name = full_caller_chain.source_form_in_universe(self._enclosing_fqun)

        if self._tracker.has_unknown_state_by_key(key):
            return

        if (
            req.required_state == action_contract.PositionOccupancyState.EMPTY
            and self._tracker.is_occupied_by_key(key)
        ):
            occupant = self._tracker.get_occupant_by_key(key)
            if isinstance(req.root_cause_quality(), ast.ActionDefinition):
                self._diagnostics.append(
                    diagnostics.ActionRequiresEmptyPositionDiagnostic(
                        location=caller_position.location,
                        action_name=req.root_cause_quality_name(),
                        position_name=position_name,
                        inferred_at=req.inferred_from.location,
                        propagated_from_locations=req.propagated_from_locations(),
                        filled_at=occupant.last_position.location,
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic(
                        location=caller_position.location,
                        create_target_name=caller_position.source_form_in_universe(
                            self._enclosing_fqun
                        ),
                        init_block_position_name=req.root_cause_quality_name(),
                        position_name=position_name,
                        inferred_at=req.inferred_from.location,
                        propagated_from_locations=req.propagated_from_locations(),
                        filled_at=occupant.last_position.location,
                    )
                )
        elif (
            req.required_state == action_contract.PositionOccupancyState.OCCUPIED
            and not self._tracker.is_occupied_by_key(key)
        ):
            if isinstance(req.root_cause_quality(), ast.ActionDefinition):
                self._diagnostics.append(
                    diagnostics.ActionRequiresOccupiedPositionDiagnostic(
                        location=caller_position.location,
                        action_name=req.root_cause_quality_name(),
                        position_name=position_name,
                        inferred_at=req.inferred_from.location,
                        propagated_from_locations=req.propagated_from_locations(),
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic(
                        location=caller_position.location,
                        create_target_name=caller_position.source_form_in_universe(
                            self._enclosing_fqun
                        ),
                        init_block_position_name=req.root_cause_quality_name(),
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
        qualities = self._get_transitive_required_qualities(position, scope)
        diags = self._executor.execute_create(
            dimension_point_operation.Create(target=position, qualities=qualities)
        )
        self._diagnostics.extend(diags)
        if diags:
            return
        self._run_position_init_blocks(position, qualities, scope)
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
        if self._tracker.has_unknown_state(stmt.target_position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, stmt.target_position, scope
        )
        diags = self._executor.execute_destroy(
            dimension_point_operation.Destroy(target=stmt.target_position)
        )
        self._diagnostics.extend(diags)

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

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, to_pos, scope
        )

        move_diagnostics = self._executor.execute_move(
            dimension_point_operation.Move(
                source=from_pos,
                target=to_pos,
                target_required_qualities=self._get_direct_required_qualities(
                    to_pos, scope
                )
                or [],
            )
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            return
        self._check_trigger(to_pos, scope)

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
                scope.get_definition(first).constraint_typed_names,
                first.full_typed_name,
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
                return
            match parent_def:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        chain,
                        child,
                        position_def.constraint_typed_names,
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
        parent: ast.GlobalTypedNameReference,
        chain: ast.PositionReference,
    ) -> ast.QualityDefinition | None:
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain unknown)."""
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
            action_def.interface_positions_by_name[
                child.full_typed_name
            ].constraint_typed_names,
            child.source_typed_name,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraints: list[ast.GlobalTypedNameReference],
        parent_name: str,
    ):
        """Check if a chain element is declared in the parent's constraints (or transitively implied by one)."""
        element_name = element.full_typed_name
        # TODO: This could be slightly more efficient by making _expand_with_implications_in_order
        # a generator and just checking as we go through if we see the name or not, I think.
        expanded = {
            name.full_typed_name
            for name in self._expand_with_implications_in_order(constraints)
        }
        if element_name not in expanded:
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_unknown(chain)

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

    def _get_direct_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> list[ast.GlobalTypedNameReference] | None:
        """Resolve the constraint qualities required at a position, in source order."""
        if scope.is_defined_local(position):
            definition = scope.get_definition(position.typed_names[0])
            return definition.constraint_typed_names

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface position definition. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position.
            parent = position.typed_names[-2]
            action_def = self._definition_results[parent.full_typed_name].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return action_def.interface_positions_by_name[
                last_element.full_typed_name
            ].constraint_typed_names

        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(last_element.full_typed_name)
        if definition_result is None:
            return None
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return position_def.constraint_typed_names

    def _get_transitive_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> list[ast.GlobalTypedNameReference]:
        direct = self._get_direct_required_qualities(position, scope)
        if direct is None:
            return []
        return self._expand_with_implications_in_order(direct)

    def _expand_with_implications_in_order(
        self, direct: list[ast.GlobalTypedNameReference]
    ) -> list[ast.GlobalTypedNameReference]:
        """Expand quality implications depth-first, implications before the implying quality.

        Order follows the spec: when a quality A implies B, B is assigned
        beforehand. Implications are walked in source order.
        """
        seen: set[str] = set()
        result: list[ast.GlobalTypedNameReference] = []

        def visit(typed_name: ast.GlobalTypedNameReference):
            name = typed_name.full_typed_name
            if name in seen:
                return
            seen.add(name)
            defn_result = self._definition_results.get(name)
            if defn_result is not None:
                for impl in defn_result.definition.quality_implications:
                    visit(impl.typed_global_name)
            result.append(typed_name)

        for typed_name in direct:
            visit(typed_name)
        return result


class ActionPostorderValidator(DefinitionPostorderValidator):
    """Validates an action definition during a DFS post-order walk."""

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
                qualities = self._get_transitive_required_qualities(trigger_ref, scope)
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._executor.execute_assume_occupied(
                    dimension_point_operation.AssumeOccupied(
                        target=trigger_ref,
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
                self._inferred_requirements,
            ),
            trigger_position_name=self._trigger_position_name or "",
        )

    @typing.override
    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # The population of the base trigger position itself is handled elsewhere
        # and doesn't create a requirement. (However, actions on children
        # of the position still do create requirements.)
        if self._trigger_position_name == position.canonical_chained_name:
            return None
        # The structural validator guarantees for us that this is defined, so
        # we don't need to re-check if it's defined.
        first = position.typed_names[0]
        if first.full_typed_name in self._interface_positions:
            return position
        return super()._chain_for_inferred_requirement(position)


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

    @typing.override
    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # Doing things with the self-reference or any of its children
        # doesn't create a requirement because _nothing_ could have run
        # before the position's own init block. Thus, we know for sure
        # that it's empty when it runs.
        if (
            position.typed_names[0].full_typed_name
            == self._definition.typed_name.full_typed_name
        ):
            return None
        return super()._chain_for_inferred_requirement(position)

    def _analyze_position_definition(
        self, definition: ast.PositionDefinition
    ) -> action_contract.PositionInitBlockContract | None:
        if definition.initialization is None:
            return None
        scope = scope_tracker.ScopeTracker()
        scope.add_definition(definition)
        self._analyze_statements(definition.initialization, scope)
        return action_contract.PositionInitBlockContract(
            requirements=self._inferred_requirements,
            guarantees=self._tracker.generate_guarantees(
                [definition.typed_name],
                self._implied_quality_list,
                self._inferred_requirements,
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
