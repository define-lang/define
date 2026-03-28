"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import abc
import typing
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

# TODO: Chains like position<local>::action</foo>::position<iface>::action</bar>::position<iface>
# are not handled. The nested action's interface positions create requirements
# and guarantees that we don't propagate through the outer action's contract, and it's not clear
# how they are supposed to propagate to callees.


class DefinitionPostorderValidator(abc.ABC):
    """Validates a single definition during a DFS post-order walk of the reference graph."""

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    _action_contracts: dict[str, action_contract.ActionContract]
    _diagnostics: list[diagnostics.Diagnostic]
    _action_body_effects: list[action_call_graph.ActionBodyEffect]

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
        action_contracts: dict[str, action_contract.ActionContract],
    ):
        """Initialize with the definition to validate and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._action_contracts = action_contracts
        self._diagnostics = []
        self._action_body_effects = []

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
    def analyze(
        self,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        list[action_call_graph.ActionBodyEffect],
        action_contract.ActionContract | None,
    ]:
        """Run post-order validation and return diagnostics, effects, and contract."""

    def _maybe_infer_requirement(  # noqa: B027
        self,
        required_state: action_contract.PositionOccupancyState,  # pyright: ignore[reportUnusedParameter]
        position: ast.PositionReference,  # pyright: ignore[reportUnusedParameter]
        scope: scope_tracker.ScopeTracker,  # pyright: ignore[reportUnusedParameter]
    ):
        """Infer a requirement for an interface position on first reference.

        No-op for non-action definitions. Overridden by ActionPostorderValidator.
        """

    def _check_trigger(
        self,
        position: ast.PositionReference,
    ):
        """Check if filling this interface position triggers the named action.

        Only triggers when the chain ends with action<...>::position<trigger>,
        i.e., we're directly filling an action's interface position.
        """
        interface_position = position.chain.get_interface_position()
        if interface_position is None:
            return
        # Only trigger when filling a single interface position directly.
        # TODO: Consider whether to support triggering on chained positions.
        if len(interface_position.chain.typed_names) != 1:
            return
        # Never None, because interface_position is not None.
        action_ref = typing.cast(
            "ast.GlobalTypedNameReference", position.chain.get_first_action()
        )
        action_name = action_ref.full_typed_name(in_universe=self._enclosing_fqun)
        # The action's file may have failed to load or parse.
        contract = self._action_contracts.get(action_name)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.chain.typed_names[0]
        )
        if trigger_element.name_content.name != contract.trigger_position_name:
            return

        self._check_requirements(position, contract)
        self._tracker.apply_guarantees(position, contract.guarantees)

    def _check_requirements(
        self,
        trigger_position: ast.PositionReference,
        contract: action_contract.ActionContract,
    ):
        """Check that all action requirements are satisfied before triggering."""
        dp = self._tracker.get_occupant(trigger_position)

        action_chain = trigger_position.chain.get_action_chain()
        if action_chain is None:
            raise ValueError(
                f"no action in chain: {trigger_position.chain.source_chained_name}"
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
                        location=dp.last_position.position,
                        action_name=action_chain.typed_names[-1].full_typed_name(
                            in_universe=self._enclosing_fqun
                        ),
                        position_name=f"{source_prefix}::{req.inferred_from.chain.source_chained_name}",
                        inferred_at=req.inferred_from.position,
                        filled_at=occupant.last_position.position,
                    )
                )
            elif (
                req.required_state == action_contract.PositionOccupancyState.OCCUPIED
                and not is_occupied
            ):
                self._diagnostics.append(
                    diagnostics.ActionRequiresOccupiedPositionDiagnostic(
                        location=dp.last_position.position,
                        action_name=action_chain.typed_names[-1].full_typed_name(
                            in_universe=self._enclosing_fqun
                        ),
                        position_name=f"{source_prefix}::{req.inferred_from.chain.source_chained_name}",
                        inferred_at=req.inferred_from.position,
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

        self._maybe_infer_requirement(
            action_contract.PositionOccupancyState.EMPTY, position, scope
        )
        if self._tracker.is_occupied(position):
            self._diagnostics.append(
                diagnostics.CreateInOccupiedPositionDiagnostic(
                    location=position.position,
                    position_name=position.chain.source_chained_name,
                    created_at=self._tracker.get_occupant(
                        position
                    ).last_position.position,
                )
            )
            return

        qualities = self._get_required_qualities(position, scope) or frozenset()
        self._tracker.create(position, qualities)
        self._check_trigger(position)

        # TODO: I'm not sure we need this anymore, I think we have a more direct
        # mechanism we could use to build the action graph.
        self._action_body_effects.append(
            action_call_graph.ActionBodyEffect(
                enclosing_typed_name=self._definition.typed_name,
                statement=stmt,
            )
        )

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
        if self._tracker.has_unknown_state(stmt.target_position):
            return
        self._action_body_effects.append(
            action_call_graph.ActionBodyEffect(
                enclosing_typed_name=self._definition.typed_name,
                statement=stmt,
            )
        )

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
        self._check_trigger(to_pos)

    def _validate_move_preconditions(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Validate occupancy, infer requirements, and check constraints.

        Returns True if the move may proceed.
        """
        self._maybe_infer_requirement(
            action_contract.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirement(
            action_contract.PositionOccupancyState.EMPTY, to_pos, scope
        )

        from_action = from_pos.chain.get_first_action()
        from_occupied = self._tracker.is_occupied(from_pos)
        to_empty = not self._tracker.is_occupied(to_pos)

        if not from_occupied:
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(from_pos)
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
                        location=from_pos.position,
                        position_name=from_pos.chain.source_chained_name,
                        inferred_at=emptied_by.position if emptied_by else None,
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyPositionDiagnostic(
                        location=from_pos.position,
                        position_name=from_pos.chain.source_chained_name,
                    )
                )
        if not to_empty:
            occupant = self._tracker.get_occupant(to_pos)
            self._diagnostics.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    location=to_pos.position,
                    position_name=to_pos.chain.source_chained_name,
                    occupied_at=occupant.last_position.position,
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
                location=to_pos.chain.typed_names[0].position,
                source_position=from_pos.chain.source_chained_name,
                target_position=to_pos.chain.source_chained_name,
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
                    location=to_chain.typed_names[-1].position,
                    position_name=to_chain.source_chained_name,
                )
            )
        else:
            divergence = to_chain.typed_names[len(from_chain.typed_names)]
            self._diagnostics.append(
                diagnostics.MoveIntoDefiningPositionDiagnostic(
                    location=divergence.position,
                    source_position=from_chain.source_chained_name,
                    target_position=to_chain.source_chained_name,
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
        chain = ref.chain
        if len(chain.typed_names) < 2:
            return
        enclosing_fqun = self._enclosing_fqun
        elements = chain.typed_names

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
        if child.name_content.name not in action_def.interface_position_constraints:
            self._emit_not_in_action_diagnostic(ref, child, parent_name, fqun)
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            ref,
            next_child,
            action_def.interface_position_constraints[child.name_content.name],
            child.full_typed_name(),
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
                    location=element.position,
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
                location=element.position,
                element_name=element.full_typed_name(in_universe=fqun),
                parent_name=parent_name,
            )
        )
        self._tracker.mark_unknown(ref)

    def _get_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> frozenset[str] | None:
        """Resolve the constraint qualities required at a position."""
        if scope.is_defined_local(position):
            return scope.get_constraint_names(position.chain.typed_names[0])

        last_element = position.chain.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface_position_constraints. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position.
            parent = position.chain.typed_names[-2]
            parent_key = parent.full_typed_name(in_universe=self._enclosing_fqun)
            action_def = self._definition_results[parent_key].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return action_def.interface_position_constraints[
                last_element.name_content.name
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
    ):
        """Initialize with the action definition to validate and the full results map."""
        super().__init__(definition_result, definition_results, action_contracts)
        self._inferred_requirements = {}

    @property
    def _action_definition(self) -> ast.ActionDefinition:
        return typing.cast("ast.ActionDefinition", self._definition)

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._action_definition.interface_positions

    @property
    def _trigger_position(self) -> ast.LocalPositionDefinition | None:
        return self._action_definition.trigger_position

    @typing.override
    def analyze(
        self,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        list[action_call_graph.ActionBodyEffect],
        action_contract.ActionContract | None,
    ]:
        """Run post-order validation and return diagnostics, effects, and contract."""
        action_def = self._action_definition
        if action_def.definition_block is not None:
            contract = self._analyze_action_definition(action_def.definition_block)
        else:
            contract = action_contract.EmptyContract()
        return self._diagnostics, self._action_body_effects, contract

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
        for condition in definition_block.trigger_conditions.conditions:
            self._validate_chained_name(condition.position_reference, scope)
            if scope.is_defined_local(condition.position_reference):
                qualities = scope.get_constraint_names(
                    condition.position_reference.chain.typed_names[0]
                )
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._tracker.create(
                    condition.position_reference, qualities, from_caller=True
                )

        scope.enter_child_scope()
        self._analyze_statements(definition_block.action_statements, scope)

        return self._generate_contract()

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=self._tracker.generate_guarantees(self._action_definition),
            trigger_position_name=(
                self._trigger_position.typed_name.name_content.name
                if self._trigger_position is not None
                else ""
            ),
        )

    @typing.override
    def _maybe_infer_requirement(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for an interface position on first reference."""
        first = position.chain.typed_names[0]
        if not isinstance(first, ast.LocalTypedNameReference):
            return
        if not scope.is_defined(first):
            return
        local_name = first.name_content.name
        if local_name not in self._interface_positions:
            return

        # Trigger position population is handled elsewhere and doesn't
        # create an implicit requirement.
        if (
            scope.is_defined_local(position)
            and self._trigger_position is not None
            and local_name == self._trigger_position.typed_name.name_content.name
        ):
            return

        requirement_key = position.chain.canonical_chained_name_tuple(
            in_universe=self._enclosing_fqun
        )
        if requirement_key in self._inferred_requirements:
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.InterfacePositionRequirement(
                required_state=required_state,
                inferred_from=position,
            )
        )

        # TODO: These checks exists here only because of a bug in how guarantees
        # are applied (they don't create requirements when they should).
        if self._tracker.is_occupied(position) or self._tracker.has_unknown_state(
            position
        ):
            return

        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            qualities = self._get_required_qualities(position, scope) or frozenset()
            self._tracker.create(position, qualities, from_caller=True)


class PositionPostorderValidator(DefinitionPostorderValidator):
    """Validates a position definition during a DFS post-order walk."""

    @typing.override
    def analyze(
        self,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        list[action_call_graph.ActionBodyEffect],
        action_contract.ActionContract | None,
    ]:
        """Run post-order validation and return diagnostics and effects."""
        definition = self._definition
        if not isinstance(definition, ast.PositionDefinition):
            raise TypeError(f"Expected PositionDefinition, got {type(definition)}")
        self._analyze_position_definition(definition)
        return self._diagnostics, self._action_body_effects, None

    def _analyze_position_definition(self, definition: ast.PositionDefinition):
        if definition.initialization is None:
            return
        scope = scope_tracker.ScopeTracker(definition.typed_name.name_content.fqun)
        scope.add_definition(definition)
        self._analyze_statements(definition.initialization, scope)


def create_postorder_validator(
    definition_result: validation_result.DefinitionValidationResult,
    definition_results: dict[str, validation_result.DefinitionValidationResult],
    action_contracts: dict[str, action_contract.ActionContract],
) -> DefinitionPostorderValidator:
    """Create the appropriate postorder validator for the given definition."""
    if isinstance(definition_result.definition, ast.ActionDefinition):
        return ActionPostorderValidator(
            definition_result, definition_results, action_contracts
        )
    if isinstance(definition_result.definition, ast.PositionDefinition):
        return PositionPostorderValidator(
            definition_result, definition_results, action_contracts
        )
    raise TypeError(f"Unexpected definition type: {type(definition_result.definition)}")
