"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _ValidatedMove:
    """Result of successful move precondition validation."""

    to_qualities: frozenset[str]
    to_external: action_contract.ActionAndInterfacePosition | None
    from_tracked: bool
    to_tracked: bool


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
        _required_state: action_contract.PositionOccupancyState,
        _local_ref: ast.LocalTypedNameReference,
        _scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for a non-trigger interface position on first reference.

        No-op for non-action definitions. Overridden by ActionPostorderValidator.
        """

    def _check_trigger(  # noqa: B027
        self,
        _ref: ast.PositionReference,
        _external: action_contract.ActionAndInterfacePosition,
    ):
        """Check if filling this interface position triggers the named action.

        No-op for non-action definitions. Overridden by ActionPostorderValidator.
        """

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

        local_ref = self._tracker.get_local_position(position, scope)
        if local_ref is not None:
            if not self._analyze_create_local(local_ref, scope):
                return
        else:
            if not self._analyze_create_chained_name(position):
                return

        # TODO: I'm not sure we need this anymore, I think we have a more direct
        # mechanism we could use to build the action graph.
        self._action_body_effects.append(
            action_call_graph.ActionBodyEffect(
                enclosing_typed_name=self._definition.typed_name,
                statement=stmt,
            )
        )

    def _analyze_create_local(
        self,
        local_ref: ast.LocalTypedNameReference,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Analyze a create statement targeting a local position.

        Returns True if the create succeeded and an effect should be recorded.
        """
        self._maybe_infer_requirement(
            action_contract.PositionOccupancyState.EMPTY,
            local_ref,
            scope,
        )
        if self._tracker.is_occupied(local_ref):
            existing = self._tracker.get_occupant(local_ref)
            self._diagnostics.append(
                diagnostics.CreateInOccupiedPositionDiagnostic(
                    position=local_ref.position,
                    position_name=local_ref.source_typed_name,
                    created_at=existing.code_position,
                )
            )
            return False
        qualities = scope.get_constraint_names(local_ref)
        self._tracker.create(local_ref, qualities)
        return True

    def _analyze_create_chained_name(
        self,
        position: ast.PositionReference,
    ) -> bool:
        """Analyze a create statement targeting a chained name position.

        Returns True if an effect should be recorded.
        """
        external = action_contract.ActionAndInterfacePosition.from_position_reference(
            position, self._enclosing_fqun
        )
        if external is None:
            return True
        if self._tracker.is_occupied(position):
            self._diagnostics.append(
                diagnostics.CreateInOccupiedPositionDiagnostic(
                    position=position.position,
                    position_name=position.chain.source_chained_name,
                    created_at=self._tracker.get_occupant(position).code_position,
                )
            )
            return False
        qualities = self._get_external_interface_position_qualities(external)
        self._tracker.create(position, qualities)
        self._check_trigger(position, external)
        return True

    def _analyze_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        validity: validation_result.DimensionPointStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_chained_name(stmt.source_position, scope)
        self._validate_chained_name(stmt.target_position, scope)
        if self._check_if_from_is_a_prefix_of_to(stmt, scope):
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

        validated = self._validate_move_preconditions(from_pos, to_pos, scope)
        if validated is None:
            return

        self._commit_move(from_pos, to_pos, validated)

    def _validate_move_preconditions(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> _ValidatedMove | None:
        """Classify positions, infer requirements, and validate occupancy and constraints.

        Returns a _ValidatedMove if the move may proceed, or None if validation failed.
        """
        from_local = self._tracker.get_local_position(from_pos, scope)
        to_local = self._tracker.get_local_position(to_pos, scope)

        from_external = (
            None
            if from_local
            else action_contract.ActionAndInterfacePosition.from_position_reference(
                from_pos,
                self._enclosing_fqun,
            )
        )
        to_external = (
            None
            if to_local
            else action_contract.ActionAndInterfacePosition.from_position_reference(
                to_pos,
                self._enclosing_fqun,
            )
        )

        # TODO: This is only necessary temporarily while we don't
        # support tracking full chained names.
        from_tracked = bool(from_local or from_external)
        to_tracked = bool(to_local or to_external)

        # Infer requirements for local interface positions.
        if from_local:
            self._maybe_infer_requirement(
                action_contract.PositionOccupancyState.OCCUPIED,
                from_local,
                scope,
            )
        if to_local:
            self._maybe_infer_requirement(
                action_contract.PositionOccupancyState.EMPTY,
                to_local,
                scope,
            )

        from_occupied = self._tracker.is_occupied(from_pos) if from_tracked else True
        to_empty = not self._tracker.is_occupied(to_pos) if to_tracked else True

        if not from_occupied:
            if from_external:
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
                        position=from_pos.position,
                        action_name=from_external.action_name,
                        position_name=from_pos.chain.source_chained_name,
                        inferred_at=self._tracker.get_emptied_by(from_pos),
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.MoveFromEmptyPositionDiagnostic(
                        position=from_pos.position,
                        position_name=from_pos.chain.source_chained_name,
                    )
                )
        if not to_empty:
            occupant = self._tracker.get_occupant(to_pos)
            self._diagnostics.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    position=to_pos.position,
                    position_name=to_pos.chain.source_chained_name,
                    occupied_at=occupant.code_position,
                )
            )

        if not (from_occupied and to_empty):
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return None

        # Resolve qualities for constraint checking. Tracked positions use the
        # tracker/scope; untracked chained positions look up the referenced definition.
        if from_tracked:
            from_qualities: frozenset[str] | None = self._tracker.get_occupant(
                from_pos
            ).qualities
        else:
            from_qualities = self._get_required_qualities_for_position(
                from_pos.chain, self._enclosing_fqun
            )
        if to_tracked:
            if to_local:
                to_qualities: frozenset[str] | None = scope.get_constraint_names(
                    to_pos.chain.typed_names[0]
                )
            else:
                to_qualities = (
                    self._get_external_interface_position_qualities(to_external)
                    if to_external
                    else None
                )
        else:
            to_qualities = self._get_required_qualities_for_position(
                to_pos.chain, self._enclosing_fqun
            )

        if not self._check_move_constraints(
            from_pos,
            to_pos,
            from_qualities,
            to_qualities,
            both_tracked=bool(from_tracked and to_tracked),
        ):
            return None

        return _ValidatedMove(
            to_qualities=to_qualities or frozenset(),
            to_external=to_external,
            from_tracked=from_tracked,
            to_tracked=to_tracked,
        )

    def _commit_move(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        validated: _ValidatedMove,
    ):
        """Update tracker state after a validated move."""
        if validated.from_tracked and validated.to_tracked:
            self._tracker.move(from_pos, to_pos)
        elif validated.from_tracked:
            self._tracker.destroy(from_pos)
        elif validated.to_tracked:
            self._tracker.create(to_pos, validated.to_qualities)

        if validated.to_external is not None:
            self._check_trigger(to_pos, validated.to_external)

    def _get_external_interface_position_qualities(
        self,
        external: action_contract.ActionAndInterfacePosition,
    ) -> frozenset[str]:
        """Get the constraint qualities for an external action's interface position."""
        definition_result = self._definition_results.get(external.action_name)
        if definition_result is None:
            return frozenset()
        action_def = definition_result.definition
        if not isinstance(action_def, ast.ActionDefinition):
            return frozenset()
        return action_def.interface_position_constraints.get(
            external.position_name, frozenset()
        )

    def _check_move_constraints(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        from_qualities: frozenset[str] | None,
        to_qualities: frozenset[str] | None,
        *,
        both_tracked: bool,
    ) -> bool:
        """Check that a move satisfies destination constraints.

        Returns True if the move may proceed (constraints satisfied or
        unresolvable). Returns False if constraints are violated and
        both positions are tracked (marks unknown state).
        """
        if from_qualities is None or to_qualities is None:
            return True
        missing = to_qualities - from_qualities
        if not missing:
            return True

        self._diagnostics.append(
            diagnostics.MoveViolatesConstraintsDiagnostic(
                position=to_pos.chain.typed_names[0].position,
                source_position=from_pos.chain.source_chained_name,
                target_position=to_pos.chain.source_chained_name,
                missing_qualities=sorted(missing),
            )
        )
        if both_tracked:
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return False
        return True

    def _check_if_from_is_a_prefix_of_to(
        self,
        stmt: ast.MoveDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
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
            if self._tracker.get_local_position(stmt.source_position, scope):
                self._tracker.mark_unknown(stmt.source_position)
            if self._tracker.get_local_position(stmt.target_position, scope):
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
                    position=element.position,
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
                position=element.position,
                element_name=element.full_typed_name(in_universe=fqun),
                parent_name=parent_name,
            )
        )
        self._tracker.mark_unknown(ref)

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
            if not isinstance(definition_result.definition, ast.PositionDefinition):
                return frozenset()
            return definition_result.definition.constraint_names
        if isinstance(definition_result.definition, ast.ActionDefinition):
            return definition_result.definition.interface_position_constraints.get(
                last_element.name_content.name, frozenset()
            )
        return frozenset()


class ActionPostorderValidator(DefinitionPostorderValidator):
    """Validates an action definition during a DFS post-order walk."""

    _inferred_requirements: dict[str, action_contract.InterfacePositionRequirement]

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
            local_position = self._tracker.get_local_position(
                condition.position_reference, scope
            )
            if local_position is not None:
                trigger_name = local_position.name_content.name
                qualities = scope.get_constraint_names(
                    condition.position_reference.chain.typed_names[0]
                )
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._tracker.create(
                    condition.position_reference,
                    qualities,
                    origin_position=self._interface_positions.get(trigger_name),
                )

        scope.enter_child_scope()
        self._analyze_statements(definition_block.action_statements, scope)

        return self._generate_contract()

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        trigger_name = (
            self._trigger_position.typed_name.name_content.name
            if self._trigger_position is not None
            else None
        )
        referenced_positions = {trigger_name} | set(self._inferred_requirements.keys())

        guarantees: dict[str, action_contract.InterfacePositionGuarantee] = {}
        for local_name, pos in self._interface_positions.items():
            if local_name not in referenced_positions:
                continue
            key = f"position<{local_name}>"

            if self._tracker.has_unknown_state_by_key(key):
                guarantees[local_name] = action_contract.UnknownGuarantee(
                    position=pos,
                )
            elif self._tracker.is_occupied_by_key(key):
                info = self._tracker.get_occupant_by_key(key)
                if info.origin_position is not None:
                    guarantees[local_name] = (
                        action_contract.OccupiedByExistingGuarantee(
                            position=pos,
                            origin_position=info.origin_position,
                            caused_by=info.code_position,
                        )
                    )
                else:
                    guarantees[local_name] = action_contract.OccupiedByNewGuarantee(
                        position=pos,
                        qualities=info.qualities,
                        caused_by=info.code_position,
                    )
            else:
                guarantees[local_name] = action_contract.EmptyGuarantee(
                    position=pos,
                    caused_by=self._tracker.get_emptied_by_key(key),
                )

        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
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
        local_ref: ast.LocalTypedNameReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for a non-trigger interface position on first reference."""
        local_name = local_ref.name_content.name
        if local_name not in self._interface_positions:
            return
        if (
            self._trigger_position is not None
            and local_name == self._trigger_position.typed_name.name_content.name
        ):
            return
        if local_name in self._inferred_requirements:
            return

        self._inferred_requirements[local_name] = (
            action_contract.InterfacePositionRequirement(
                position=self._interface_positions[local_name],
                required_state=required_state,
                inferred_from=local_ref.position,
            )
        )

        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            qualities = scope.get_constraint_names(local_ref)
            self._tracker.create(
                local_ref,
                qualities,
                origin_position=self._interface_positions.get(local_name),
            )

    @typing.override
    def _check_trigger(
        self,
        ref: ast.PositionReference,
        external: action_contract.ActionAndInterfacePosition,
    ):
        """Check if filling this interface position triggers the named action."""
        contract = self._action_contracts.get(external.action_name)
        if contract is None:
            return
        if external.position_name != contract.trigger_position_name:
            return

        self._check_requirements(ref, external.action_name, contract)
        self._tracker.apply_guarantees(ref, contract.guarantees)

    def _check_requirements(
        self,
        trigger_position: ast.PositionReference,
        action_name: str,
        contract: action_contract.ActionContract,
    ):
        """Check that all action requirements are satisfied before triggering."""
        dp = self._tracker.get_occupant(trigger_position)

        chain_prefix = "::".join(
            e.source_typed_name for e in trigger_position.chain.typed_names[:-1]
        )

        for req in contract.requirements.values():
            req_name = req.position.typed_name.name_content.name
            key = self._tracker.interface_position_key(trigger_position, req_name)

            if self._tracker.has_unknown_state_by_key(key):
                continue

            is_occupied = self._tracker.is_occupied_by_key(key)
            req_chained_name = (
                f"{chain_prefix}::{req.position.typed_name.source_typed_name}"
            )

            if (
                req.required_state == action_contract.PositionOccupancyState.EMPTY
                and is_occupied
            ):
                occupant = self._tracker.get_occupant_by_key(key)
                self._diagnostics.append(
                    diagnostics.ActionRequiresEmptyPositionDiagnostic(
                        position=dp.code_position,
                        action_name=action_name,
                        position_name=req_chained_name,
                        inferred_at=req.inferred_from,
                        filled_at=occupant.code_position,
                    )
                )
            elif (
                req.required_state == action_contract.PositionOccupancyState.OCCUPIED
                and not is_occupied
            ):
                self._diagnostics.append(
                    diagnostics.ActionRequiresOccupiedPositionDiagnostic(
                        position=dp.code_position,
                        action_name=action_name,
                        position_name=req_chained_name,
                        inferred_at=req.inferred_from,
                    )
                )


class PositionPostorderValidator(DefinitionPostorderValidator):
    """Validates a position definition during a DFS post-order walk."""

    # TODO: Position init blocks should also check triggers when creating/moving
    # into external action interface positions. Currently _check_trigger is a
    # no-op for position definitions.

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
