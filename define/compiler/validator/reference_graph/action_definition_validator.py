"""Post-order validation for a single action definition during the reference graph DFS walk."""

from __future__ import annotations

import typing
from functools import cached_property

from define.compiler import (
    ast,
    chained_name,
    encoding_operation_associations,
    name_types,
)
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input, scope_tracker, validation_result
from define.compiler.validator.reference_graph import (
    action_contract,
    action_requirement_validator,
    chained_name_validator,
    literal_encoder,
    operation_arguments_validator,
    particle_operation_validator,
    position_occupancy,
    position_quality_resolver,
    quality_assignment,
    reference_graph_validation_state,
)
from define.compiler.validator.reference_graph.callee_execution import (
    callee_execution,
    callee_execution_validator,
)
from define.compiler.validator.reference_graph.dead_code import (
    dead_constraint_validator,
    dead_value_write_validator,
)
from define.compiler.validator.reference_graph.destruction import (
    destroyed_particles,
    destroyer,
    destruction_contract_validator,
    destructor_guarantees,
    guaranteed_particle_destruction,
)
from define.compiler.validator.reference_graph.destruction import (
    destruction_contract as destruction_contract_types,
)
from define.compiler.validator.reference_graph.particles import (
    particle_info,
    particle_tracker,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence

    from define.compiler.data_structures import typed_name_dict


class ActionDefinitionValidator:
    """Validates an action definition during a DFS post-order walk of the reference graph."""

    _definition: ast.ActionDefinition
    _particle_statement_validity: Sequence[validation_result.ParticleStatementValidity]
    _looked_at_position_validity: Sequence[bool]
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _diagnostics: list[diagnostics.Diagnostic]
    _destruction_contracts: list[action_contract.DestructionContracts]

    def __init__(
        self,
        definition: ast.ActionDefinition,
        particle_statement_validity: Sequence[
            validation_result.ParticleStatementValidity
        ],
        looked_at_position_validity: Sequence[bool],
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
    ):
        """Initialize with the Action Definition, statement validity, and known definitions."""
        self._definition = definition
        self._particle_statement_validity = particle_statement_validity
        self._looked_at_position_validity = looked_at_position_validity
        self._definition_results = definition_results
        self._validation_state = validation_state
        self._diagnostics = []
        self._destruction_contracts = []
        self._steps: list[codegen_input.ActionStep] = []

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> particle_tracker.ParticleTracker:
        return particle_tracker.ParticleTracker()

    @cached_property
    def _operation_validator(
        self,
    ) -> particle_operation_validator.ParticleOperationValidator:
        return particle_operation_validator.ParticleOperationValidator(
            self._tracker, self._enclosing_fqun
        )

    @cached_property
    def _literal_encoder(self) -> literal_encoder.LiteralEncoder:
        return literal_encoder.LiteralEncoder(
            self._definition_results, self._enclosing_fqun
        )

    @cached_property
    def _operation_arguments_validator(
        self,
    ) -> operation_arguments_validator.OperationArgumentsValidator:
        return operation_arguments_validator.OperationArgumentsValidator(
            self._definition_results, self._enclosing_fqun, self._literal_encoder
        )

    @cached_property
    def _chained_name_validator(self) -> chained_name_validator.ChainedNameValidator:
        return chained_name_validator.ChainedNameValidator(
            self._definition_results, self._tracker
        )

    @cached_property
    def _destruction_contract_validator(
        self,
    ) -> destruction_contract_validator.DestructionContractValidator:
        return destruction_contract_validator.DestructionContractValidator(
            self._definition,
            self._definition_results,
            self._validation_state,
            self._tracker,
            self._dead_value_write_validator,
            self._destroyed_particles,
        )

    @cached_property
    def _position_quality_resolver(
        self,
    ) -> position_quality_resolver.PositionQualityResolver:
        return position_quality_resolver.PositionQualityResolver(
            self._definition,
            self._definition_results,
            self._validation_state,
        )

    @cached_property
    def _dead_value_write_validator(
        self,
    ) -> dead_value_write_validator.DeadValueWriteValidator:
        return dead_value_write_validator.DeadValueWriteValidator(self._tracker)

    @cached_property
    def _dead_constraint_validator(
        self,
    ) -> dead_constraint_validator.DeadConstraintValidator:
        return dead_constraint_validator.DeadConstraintValidator(
            self._definition_results,
            self._tracker,
            self._position_quality_resolver,
        )

    @cached_property
    def _requirement_validator(
        self,
    ) -> action_requirement_validator.ActionRequirementValidator:
        return action_requirement_validator.ActionRequirementValidator(
            self._definition,
            self._tracker,
            self._position_quality_resolver,
        )

    @cached_property
    def _callee_execution_validator(
        self,
    ) -> callee_execution_validator.CalleeExecutionValidator:
        return callee_execution_validator.CalleeExecutionValidator(
            self._definition,
            self._tracker,
            self._requirement_validator,
            self._dead_constraint_validator,
            self._dead_value_write_validator,
            self._destruction_contract_validator,
        )

    @cached_property
    def _destroyer(self) -> destroyer.Destroyer:
        return destroyer.Destroyer(
            self._destroyed_particles,
            self._tracker,
            self._callee_execution_validator,
            self._validation_state,
        )

    @cached_property
    def _destroyed_particles(self) -> destroyed_particles.DestroyedParticles:
        return destroyed_particles.DestroyedParticles(
            self._tracker, self._definition_results
        )

    @cached_property
    def _implied_quality_list(self) -> tuple[ast.GlobalTypedNameReference, ...]:
        return tuple(
            impl.typed_global_name for impl in self._definition.quality_implications
        )

    def _action_definition(
        self, quality: ast.GlobalTypedNameReference
    ) -> ast.ActionDefinition | None:
        """Return the definition of an action quality, or None if it is unresolved."""
        definition_result = self._definition_results.get(quality)
        if definition_result is None:
            return None
        return typing.cast("ast.ActionDefinition", definition_result.definition)

    def _run_constructors(
        self,
        statement: ast.CreateParticleStatement,
        qualities: quality_assignment.QualityAssignments,
        scope: scope_tracker.ScopeTracker,
    ):
        """Trigger every constructor on the particle just created in position (DLP 32)."""
        position = statement.target_position
        for quality in qualities.assignments:
            if quality.name_type != name_types.NameType.ACTION:
                continue
            definition = self._action_definition(quality)
            # The constructor's file may have failed to load or parse, which is
            # reported elsewhere; skipping it here keeps destruction analysis
            # from failing on an already-reported error.
            if definition is None:
                continue
            if not definition.is_constructor:
                continue
            parent_particle = self._tracker.get_occupant(position)
            self._dead_constraint_validator.mark_action_alive(
                quality, position, parent_particle
            )
            contract = self._validation_state.get_contract_or_none(quality)
            # A rejected circular reference can leave this constructor's contract
            # unpublished while the referencing definition is validated.
            if contract is None:
                continue
            # The constructor is a quality of the particle in `position`, so its
            # interface positions hang off position::action</construct> while its
            # implied qualities hang off the position itself.
            self._trigger_callee(
                callee_execution.ConstructorCalleeExecution(
                    contract=contract,
                    action_chain=position.with_action_suffix(quality),
                    parent_particle=parent_particle,
                    acting_on_position=position,
                ),
                scope,
            )

    def _destroy_particles(
        self,
        targets: Sequence[destroyer.DestructionTarget],
        scope: scope_tracker.ScopeTracker,
    ):
        """Destroy the target particles and every particle below them."""
        result = self._destroyer.destroy(targets, scope)
        self._diagnostics.extend(result.diagnostics)
        self._destruction_contracts.extend(result.destruction_contracts)
        self._steps.append(result.step)

    def _process_interface_arrival(
        self,
        statement: ast.CreateParticleStatement | ast.MoveParticleStatement,
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Record an interface arrival and trigger its action if appropriate."""
        position = statement.target_position
        particle = self._tracker.get_occupant(position)
        action = action_chain.get_last_action()
        contract = self._validation_state.get_contract_or_none(action)
        if contract is None:
            return
        # Only trigger when filling a single interface position directly,
        # not children of interface positions.
        if len(position.typed_names) != len(action_chain.typed_names) + 1:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", position.typed_names[-1]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
            return

        parent_position = action_chain.parent_position()
        parent_particle = None
        # A chain with no parent position starts with one of this action's
        # implied actions, which triggers on this action's parent particle.
        if parent_position is None:
            self._dead_constraint_validator.mark_implied_action_alive(action)
        else:
            parent_particle = self._tracker.get_occupant(parent_position)
            self._dead_constraint_validator.mark_action_alive(
                action, parent_position, parent_particle
            )
        self._dead_constraint_validator.mark_contract_position_constraints_alive(
            position, particle, scope
        )

        self._trigger_callee(
            callee_execution.CalleeExecution(
                contract=contract,
                action_chain=action_chain,
                parent_particle=parent_particle,
                acting_on_position=particle.last_position,
            ),
            scope,
        )

    def _trigger_callee(
        self,
        execution: callee_execution.CalleeExecution,
        scope: scope_tracker.ScopeTracker,
    ):
        result = self._callee_execution_validator.validate(execution, scope)
        self._diagnostics.extend(result.diagnostics)
        self._steps.append(result.codegen_execution)
        self._destruction_contracts.extend(result.destruction_contracts)

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        validity_iter = iter(self._particle_statement_validity)
        looked_at_validity_iter = iter(self._looked_at_position_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.ValueSettingStatement():
                    validity = next(validity_iter)
                    self._analyze_value_setting(stmt, validity, scope)
                case ast.LocalPositionDefinition():
                    self._steps.append(stmt)
                    scope.add_definition(stmt)
                    self._dead_constraint_validator.register_position_constraints(stmt)
                case ast.CreateParticleStatement():
                    self._steps.append(stmt)
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope)
                case ast.MoveParticleStatement():
                    self._steps.append(stmt)
                    validity = next(validity_iter)
                    self._analyze_move(stmt, validity, scope)
                case ast.DestroyParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_destroy(stmt, validity, scope)
                case ast.OperationExecutionStatement():
                    self._analyze_operation_execution(
                        stmt, looked_at_validity_iter, scope
                    )
        self._auto_destruct_locals(scope)

    def _auto_destruct_locals(self, scope: scope_tracker.ScopeTracker):
        """Destroy any particles still in positions defined locally in this block.

        Per the spec's "Automatic Destruction" section, all particles still
        occupying Positions defined only within this block are simultaneously
        automatically destroyed.
        """
        targets: list[destroyer.DestructionTarget] = []
        for definition in scope.current_scope_definitions():
            position = ast.PositionReference(
                typed_names=(definition.typed_name,),
                location=definition.location,
            )
            # Spec: "If the compiler is uncertain about whether a position still
            # contains a particle, it only destroys the particle if
            # one is present."
            occupancy = self._tracker.get_occupancy_info(position)
            if occupancy.has_error or occupancy.occupant is None:
                continue
            auto_destruction_target = occupancy.occupant.last_position
            targets.append(
                destroyer.DestructionTarget(
                    destruction=destruction_contract_types.DirectDestruction(
                        directly_destroyed_position=position,
                        destroying_action=self._definition.typed_name,
                        is_automatic=True,
                    ),
                    auto_destruction_target=auto_destruction_target,
                )
            )
        self._destroy_particles(targets, scope)

    def _analyze_value_setting(
        self,
        stmt: ast.ValueSettingStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not (validity.target_ok and validity.source_ok):
            return
        positions = (stmt.target_position,)
        if isinstance(stmt.source, ast.PositionReference):
            positions = (stmt.target_position, stmt.source)
        for position in positions:
            self._dead_constraint_validator.mark_referenced_position_constraints_alive(
                position
            )
            self._diagnostics.extend(
                self._chained_name_validator.validate(position, scope)
            )
        if (
            isinstance(stmt.source, ast.PositionReference)
            and stmt.target_position.canonical_chained_name_tuple
            == stmt.source.canonical_chained_name_tuple
        ):
            return
        for position in positions:
            if not self._tracker.has_error_state(position):
                self._requirement_validator.infer_requirements_on_chain(
                    position_occupancy.PositionOccupancyState.OCCUPIED, position, scope
                )
                self._dead_constraint_validator.mark_value_and_encoding_constraints_alive(
                    position
                )
        if isinstance(stmt.source, ast.PositionReference):
            self._requirement_validator.infer_value_requirement(
                stmt.source, inferred_at=stmt.source.location
            )
            self._dead_value_write_validator.mark_used(stmt.source)
        value_diagnostics, value_state, target_type = (
            self._operation_validator.validate_value_setting(
                stmt.target_position, stmt.source
            )
        )
        self._diagnostics.extend(value_diagnostics)
        has_errors = bool(value_diagnostics)
        match stmt.source:
            case ast.Literal():
                # A literal can only be encoded once the value type it sets is
                # known.
                if target_type is not None:
                    value, literal_diagnostics = self._literal_encoder.encode(
                        stmt.source, target_type
                    )
                    self._diagnostics.extend(literal_diagnostics)
                    has_errors = has_errors or bool(literal_diagnostics)
                    if value is not None:
                        self._steps.append(
                            codegen_input.LiteralValueSetting(
                                target_position=stmt.target_position,
                                value_type=target_type,
                                value=value,
                            )
                        )
            case ast.PositionReference():
                # Validation reports a target without a known value type.
                if target_type is not None:
                    self._steps.append(
                        codegen_input.PositionValueSetting(
                            target_position=stmt.target_position,
                            value_type=target_type,
                            source_position=stmt.source,
                        )
                    )
        if any(self._tracker.has_error_state(position) for position in positions):
            return
        # A failed statement still counts as writing its target, so later
        # reads do not report the same mistake again as an unset value.
        if has_errors:
            if target_type is not None:
                self._tracker.mark_value_error(stmt.target_position)
            return
        self._tracker.set_value(stmt.target_position, value_state)
        # Copying a value that already has an error does not write a new value,
        # so it is not reported again as a dead write.
        if value_state != particle_info.ParticleValueState.ERROR:
            self._diagnostics.extend(
                self._dead_value_write_validator.record_write(stmt.target_position)
            )

    def _analyze_operation_execution(
        self,
        stmt: ast.OperationExecutionStatement,
        looked_at_validity: Iterator[bool],
        scope: scope_tracker.ScopeTracker,
    ):
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        executed = self._operation_arguments_validator.get_executed_operation(stmt)
        looked_at_qualities: dict[ast.OperationArgumentStatement, Collection[str]] = {}
        written_positions: list[ast.PositionReference] = []
        for argument in stmt.arguments:
            position = argument.looking_at
            if not isinstance(position, ast.PositionReference):
                continue
            if not next(looked_at_validity):
                continue
            interface_view = (
                None
                if executed is None
                else executed.get_view(argument.view.source_typed_name)
            )
            # A missing operation or an undefined interface view is reported
            # when the arguments are validated, so its position is neither
            # read nor written.
            is_read = interface_view is not None and interface_view.is_input
            particle = self._analyze_looked_at_position(
                position, scope, statement_diagnostics, is_read=is_read
            )
            if particle is None:
                continue
            looked_at_qualities[argument] = particle.qualities.names
            if (
                interface_view is not None
                and interface_view.is_output
                and particle.qualities.value_type is not None
            ):
                written_positions.append(position)
        argument_diagnostics, literal_values = (
            self._operation_arguments_validator.validate(stmt, looked_at_qualities)
        )
        statement_diagnostics.extend(argument_diagnostics)
        self._diagnostics.extend(statement_diagnostics)
        # A failed statement still counts as writing its output views, so
        # later reads do not report the same mistake again as an unset value.
        for position in written_positions:
            if statement_diagnostics:
                self._tracker.mark_value_error(position)
            else:
                self._tracker.set_value(position, particle_info.ParticleValueState.SET)
                self._diagnostics.extend(
                    self._dead_value_write_validator.record_write(position)
                )
        if executed is None or statement_diagnostics:
            return
        encoding_operation = (
            encoding_operation_associations.encoding_operation_reference(
                # Actions can only execute Value Operations.
                typing.cast("ast.ValueOperationDefinition", executed)
            )
        )
        # TODO: Once users can define Value Operations and Encoding Operations
        # that associate, report executing a Value Operation that no Encoding
        # Operation performs. Code generation relies on every executed Value
        # Operation having one.
        if encoding_operation is None:
            return
        arguments = self._operation_arguments_validator.operation_arguments(
            stmt, executed, literal_values, ast.PositionReference
        )
        if arguments is not None:
            self._steps.append(
                codegen_input.ActionOperationExecution(
                    operation=stmt.operation,
                    encoding_operation=encoding_operation,
                    arguments=arguments,
                )
            )

    def _analyze_looked_at_position(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        statement_diagnostics: list[diagnostics.Diagnostic],
        *,
        is_read: bool,
    ) -> particle_info.ParticleInfo | None:
        """Validate a position looked at by an Operation Argument Statement, and return its particle when it can be checked further.

        Diagnostics are added to ``statement_diagnostics``.
        """
        self._dead_constraint_validator.mark_referenced_position_constraints_alive(
            position
        )
        statement_diagnostics.extend(
            self._chained_name_validator.validate(position, scope)
        )
        if self._tracker.has_error_state(position):
            return None
        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED, position, scope
        )
        self._dead_constraint_validator.mark_value_and_encoding_constraints_alive(
            position
        )
        if is_read:
            self._requirement_validator.infer_value_requirement(
                position, inferred_at=position.location
            )
            self._dead_value_write_validator.mark_used(position)
        diagnostic = self._operation_validator.validate_looked_at(
            position, is_read=is_read
        )
        if diagnostic is not None:
            statement_diagnostics.append(diagnostic)
        return self._tracker.get_occupant_or_none(position)

    def _analyze_create(
        self,
        stmt: ast.CreateParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._dead_constraint_validator.mark_referenced_position_constraints_alive(
            stmt.target_position
        )
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
        position = stmt.target_position
        if self._tracker.has_error_state(position):
            return

        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.EMPTY, position, scope
        )
        qualities = self._position_quality_resolver.get_transitive_required_qualities(
            position, scope
        )
        diagnostic = self._operation_validator.validate_create(position)
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            return
        self._tracker.create(position, qualities)
        self._run_constructors(stmt, qualities, scope)
        self._check_trigger(stmt, scope)

    def _analyze_destroy(
        self,
        stmt: ast.DestroyParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._dead_constraint_validator.mark_referenced_position_constraints_alive(
            stmt.target_position
        )
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
        if self._tracker.has_error_state(stmt.target_position):
            return

        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED,
            stmt.target_position,
            scope,
        )
        diagnostic = self._operation_validator.validate_destroy(stmt.target_position)
        if diagnostic is not None:
            self._diagnostics.append(diagnostic)
            return
        destruction = destruction_contract_types.DirectDestruction(
            directly_destroyed_position=stmt.target_position,
            destroying_action=self._definition.typed_name,
            is_automatic=False,
        )

        self._destroy_particles(
            (
                destroyer.DestructionTarget(
                    destruction=destruction, auto_destruction_target=None
                ),
            ),
            scope,
        )

    def _analyze_move(
        self,
        stmt: ast.MoveParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not (validity.source_ok and validity.target_ok):
            return
        if validity.from_is_prefix_of_to:
            self._tracker.mark_error(stmt.source_position)
            self._tracker.mark_error(stmt.target_position)
            return
        self._dead_constraint_validator.mark_referenced_position_constraints_alive(
            stmt.source_position
        )
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.source_position, scope)
        )
        self._dead_constraint_validator.mark_referenced_position_constraints_alive(
            stmt.target_position
        )
        self._diagnostics.extend(
            self._chained_name_validator.validate(stmt.target_position, scope)
        )
        if (
            stmt.source_position.canonical_chained_name_tuple
            == stmt.target_position.canonical_chained_name_tuple
        ):
            # We can't execute self-to-self moves because it would re-trigger
            # actions if the move is for a trigger position.
            return
        self._execute_move(stmt, scope)

    def _execute_move(
        self,
        stmt: ast.MoveParticleStatement,
        scope: scope_tracker.ScopeTracker,
    ):
        """Execute a move and update tracker state."""
        from_pos = stmt.source_position
        to_pos = stmt.target_position
        if self._tracker.has_error_state(from_pos) or self._tracker.has_error_state(
            to_pos
        ):
            self._tracker.mark_error(from_pos)
            self._tracker.mark_error(to_pos)
            return

        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.EMPTY, to_pos, scope
        )

        target_required_qualities = (
            self._position_quality_resolver.get_direct_required_qualities(to_pos, scope)
        )
        move_diagnostics = self._operation_validator.validate_move(
            source=from_pos,
            target=to_pos,
            target_required_qualities=target_required_qualities or (),
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            return
        self._tracker.move(from_pos, to_pos)
        self._check_trigger(stmt, scope)

    @property
    def _trigger_position_name(self) -> str | None:
        if self._definition.trigger_position is not None:
            return self._definition.trigger_position.typed_name.full_typed_name
        return None

    def analyze(
        self,
    ) -> validation_result.ActionPostorderValidationResult:
        """Run post-order validation and return diagnostics, contract, and codegen input."""
        contract, guaranteed_particle_destructors = self._analyze_action_definition()
        propagated_destructions: list[
            destruction_contract_types.PropagatedDestruction
        ] = []
        for contracts in contract.destruction_contracts:
            for destruction_contract in contracts.particles:
                propagated_destructions.append(
                    destruction_contract.propagated_destruction
                )
        return validation_result.ActionPostorderValidationResult(
            diagnostics=self._diagnostics,
            contract=contract,
            codegen_input=codegen_input.ActionCodegenInput(
                definition=self._definition,
                steps=self._steps,
                propagated_destructions=propagated_destructions,
                guaranteed_particle_destructors=guaranteed_particle_destructors,
            ),
        )

    def _check_trigger(
        self,
        statement: ast.CreateParticleStatement | ast.MoveParticleStatement,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        position = statement.target_position
        action_chain = position.get_chain_to_last_action()
        if action_chain is not None:
            self._process_interface_arrival(statement, action_chain, scope)
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
    ) -> tuple[
        action_contract.ActionContract,
        list[codegen_input.GuaranteedParticleDestructors],
    ]:
        scope = scope_tracker.ScopeTracker()
        self._dead_constraint_validator.register_implied_actions(
            self._definition.quality_implications
        )
        for pos in self._definition.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)
                self._dead_constraint_validator.register_position_constraints(pos)

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._definition.trigger_position_reference
        if trigger_ref is not None:
            qualities = (
                self._position_quality_resolver.get_transitive_required_qualities(
                    trigger_ref, scope
                )
            )
            # DLP 37: We assume trigger points are occupied upon the start
            # of the action, but we can only assume they have the qualities
            # they are declared with.
            self._tracker.assume_occupied(
                trigger_ref,
                qualities,
                position_in_caller=trigger_ref,
            )

        scope.enter_child_scope()
        self._analyze_statements(self._definition.action_statements, scope)
        self._check_unconsumed_action_interfaces()

        guaranteed_destruction = (
            guaranteed_particle_destruction.guaranteed_particle_destruction(
                self._definition,
                self._position_quality_resolver.get_transitive_implied_qualities(
                    self._implied_quality_list
                ),
                self._destroyed_particles,
                self._validation_state,
                self._tracker,
            )
        )
        contract, guarantees = self._generate_contract(
            guaranteed_destruction.on_destruction
        )
        self._diagnostics.extend(
            self._dead_constraint_validator.validate(guarantees, scope)
        )
        self._diagnostics.extend(self._dead_value_write_validator.validate(guarantees))
        return (
            contract,
            guaranteed_destruction.guaranteed_particle_destructors,
        )

    def _check_unconsumed_action_interfaces(self):
        """Diagnose occupied interface positions of actions triggered by this action."""
        for triggered_at, position in self._tracker.unconsumed_action_interfaces():
            self._diagnostics.append(
                diagnostics.UnconsumedActionInterfaceDiagnostic(
                    location=triggered_at,
                    # The action whose interface position this is comes just
                    # before it in the chained name.
                    action_name=ast.source_form_chained_name(
                        chained_name.ChainedNameTuple(position[-2:-1]),
                        self._enclosing_fqun.canonical,
                    ),
                    position_name=ast.source_form_chained_name(
                        position, self._enclosing_fqun.canonical
                    ),
                )
            )

    def _generate_contract(
        self,
        on_destruction: dict[
            chained_name.PositionReferenceTuple, action_contract.OnDestruction
        ],
    ) -> tuple[
        action_contract.ActionContract,
        dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionGuarantee,
        ],
    ]:
        """Generate the action contract from inferred requirements and final tracker state.

        Also returns the action's own Guarantees, by position.
        """
        requirements = self._requirement_validator.occupancy_requirements
        guarantees = self._tracker.generate_own_guarantees(
            self._definition.interface_position_names,
            self._implied_quality_list,
            requirements,
        )
        destruction_contracts = self._destruction_contracts
        if self._definition.is_destructor:
            self._diagnostics.extend(
                destructor_guarantees.check_destructor_guarantees(
                    guarantees, self._tracker, self._enclosing_fqun
                )
            )
            # A Destructor may not destroy a particle from its caller either,
            # so it publishes no Destruction Contracts for one; each is
            # already reported as a forbidden Guarantee.
            destruction_contracts = []
        contract = action_contract.ActionContract(
            occupancy_requirements=list(requirements.values()),
            value_requirements=list(
                self._requirement_validator.value_requirements.values()
            ),
            guarantees=self._tracker.published_guarantees(
                self._definition.typed_name, guarantees, on_destruction
            ),
            destruction_contracts=destruction_contracts,
            trigger_position_name=self._trigger_position_name or "",
            implied_quality_names=(
                self._position_quality_resolver.get_transitive_implied_quality_names(
                    self._implied_quality_list
                )
            ),
        )
        return contract, guarantees
