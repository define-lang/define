"""Pure per-definition validation for the Define language."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import (
    ast,
    config,
    constants,
    encoding_operation_associations,
    name_types,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics
from define.compiler.graphs import reference_graph
from define.compiler.validator import scope_tracker, validation_result
from define.compiler.validator.structural import (
    name_validators,
    view_setting_order_tracker,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from define.compiler.validator.structural import file_validation_context


class DefinitionStructuralValidator:
    """Validates one definition within a single file.

    Is mutable and not thread-safe.
    """

    _context: file_validation_context.FileValidationContext
    _diagnostics: list[diagnostics.Diagnostic]
    _definition: ast.GlobalDefinition
    _reference_edges: list[reference_graph.ReferenceEdge]
    _seen_edge_targets: set[str]
    # The source typed names that already validated without diagnostics in
    # this definition.
    _valid_typed_names: set[str]
    _particle_statement_validity: list[validation_result.ParticleStatementValidity]
    _looked_at_position_validity: list[bool]
    _unknown_fquns: set[str]
    _implied_qualities: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameReference, ast.QualityImplicationStatement
    ]
    _used_implied_qualities: set[str]
    _unreferenced_positions: typed_name_dict.TypedNameDict[
        ast.LocalTypedNameReference, ast.LocalPositionDefinition
    ]
    _unreferenced_views: typed_name_dict.TypedNameDict[
        ast.LocalTypedNameReference,
        ast.InterfaceViewDefinition | ast.LocalViewDefinition,
    ]

    def __init__(
        self,
        definition: ast.GlobalDefinition,
        context: file_validation_context.FileValidationContext,
    ):
        """Initialize per-definition validation state from file-level state."""
        self._definition = definition
        self._context = context
        self._diagnostics = []
        self._reference_edges = []
        self._seen_edge_targets = set()
        self._valid_typed_names = set()
        self._particle_statement_validity = []
        self._looked_at_position_validity = []
        self._unknown_fquns = set()
        self._implied_qualities = typed_name_dict.TypedNameDict()
        self._used_implied_qualities = set()
        self._unreferenced_positions = typed_name_dict.TypedNameDict()
        self._unreferenced_views = typed_name_dict.TypedNameDict()

    def validate_definition(self) -> validation_result.DefinitionValidationResult:
        """Validate one top-level definition and return its validation result."""
        self._diagnostics.extend(
            name_validators.validate_global_name(
                self._definition.typed_name.name_content,
                # TODO: Remove this special case once the Define Standard
                # Library exists.
                allow_reserved_universe=(
                    self._context.root_prefix == constants.STANDARD_LIBRARY_ROOT
                ),
            )
        )

        match self._definition:
            case ast.ActionDefinition() as definition:
                self._validate_action_definition(definition)
            case ast.PositionDefinition() as definition:
                self._validate_quality_assignment_block(
                    definition.quality_assignment_block
                )
            case ast.PotentialLiteralDefinition() as definition:
                encoding = definition.encoding
                encoding_diagnostics = self._typed_name_diagnostics(encoding)
                self._diagnostics.extend(encoding_diagnostics)
                if not encoding_diagnostics:
                    self._process_reference(encoding)
            case ast.OperationDefinition() as definition:
                self._validate_operation_definition(definition)
            case ast.LogicalOperationDefinition() as definition:
                self._validate_logical_operation_definition(definition)
            case ast.ValueDefinition() as definition:
                self._validate_logical_operation_support_statements(
                    definition.logical_operation_support_statements
                )
            case _:
                pass
        return self.build_result()

    def build_result(self) -> validation_result.DefinitionValidationResult:
        """Build a result object from the validator's private state."""
        return validation_result.DefinitionValidationResult(
            definition=self._definition,
            diagnostics=self._diagnostics,
            reference_edges=self._reference_edges,
            particle_statement_validity=self._particle_statement_validity,
            looked_at_position_validity=self._looked_at_position_validity,
        )

    def _validate_action_definition(
        self,
        definition: ast.ActionDefinition,
    ):
        self._validate_quality_implications(definition.quality_implications)
        scope = scope_tracker.PositionScopeTracker()
        for local_def in definition.interface_positions:
            self._validate_local_position_definition(local_def, scope)
        self._validate_trigger_conditions(definition.trigger_conditions, scope)
        scope.enter_child_scope()
        self._validate_action_statements(
            definition.action_statements,
            scope,
        )
        self._check_unreferenced_positions()
        self._check_unused_quality_implications()

    def _validate_operation_definition(self, definition: ast.OperationDefinition):
        if isinstance(definition, ast.ValueOperationDefinition):
            # Executing a Value Operation executes the Encoding Operation that
            # performs it, so the Value Operation references that Encoding
            # Operation.
            encoding_operation = (
                encoding_operation_associations.encoding_operation_reference(definition)
            )
            if encoding_operation is not None:
                self._process_reference(encoding_operation)
        views = scope_tracker.ScopeTracker[
            ast.InterfaceViewDefinition | ast.LocalViewDefinition
        ]()
        for view in definition.views:
            self._validate_view_definition(definition, view, views)
        views.enter_child_scope()
        executes_all_views = False
        has_execution = False

        def validate_looked_at(looking_at: ast.LocalTypedNameReference) -> bool:
            return self._validate_looked_at_view(looking_at, views)

        view_setting_order = view_setting_order_tracker.ViewSettingOrderTracker()
        for statement in definition.operation_statements.statements:
            if not isinstance(statement, ast.ViewSettingStatement):
                self._diagnostics.extend(
                    view_setting_order.check_next_statement(statement)
                )
            match statement:
                case ast.LocalViewDefinition():
                    self._validate_view_definition(definition, statement, views)
                case ast.OperationExecutionStatement():
                    has_execution = True
                    _ = self._validate_execution(
                        statement.operation, statement.arguments, validate_looked_at
                    )
                case ast.LogicalOperationExecutionStatement():
                    has_execution = True
                    if self._validate_execution(
                        statement.logical_operation,
                        statement.arguments,
                        validate_looked_at,
                    ):
                        # Executing a logical operation executes one of the
                        # Encoding Operations that perform it, so the
                        # execution references all of them.
                        # TODO: Load only the Encoding Operation chosen for
                        # each instance's encodings, instead of every
                        # candidate. That needs the association table to
                        # state each Encoding Operation's encodings, so the
                        # choice needs no loading, and loading during
                        # reference graph validation, when instances are
                        # built.
                        for encoding_operation in encoding_operation_associations.logical_operation_encoding_operation_references(
                            statement.logical_operation.full_typed_name,
                            statement.logical_operation.location,
                            definition.typed_name.name_content.fqun,
                        ):
                            self._process_reference(encoding_operation)
                case ast.ViewSettingStatement():
                    self._validate_view_setting(
                        definition,
                        statement,
                        views,
                        view_setting_order,
                    )
                case (
                    ast.EncodingOperationExecutionStatement()
                    | ast.ComputerOperationExecutionStatement()
                ):
                    has_execution = True
                    executes_all_views = True
        self._diagnostics.extend(view_setting_order.check_operation_end())
        if not has_execution:
            self._diagnostics.append(
                diagnostics.OperationWithoutExecutionDiagnostic(
                    location=definition.operation_statements.location
                )
            )
        for view in self._unreferenced_views.values():
            if isinstance(view, ast.LocalViewDefinition):
                self._diagnostics.append(
                    diagnostics.UnreferencedLocalViewDiagnostic(
                        location=view.typed_name.location,
                        view_name=view.typed_name.source_typed_name,
                    )
                )
            # The encoding operation or computer operation receives every
            # interface view, so executing it references all of them.
            elif not executes_all_views:
                self._diagnostics.append(
                    diagnostics.UnreferencedViewDiagnostic(
                        location=view.typed_name.location,
                        view_name=view.typed_name.source_typed_name,
                        operation_name_type=definition.typed_name.name_type,
                    )
                )

    def _validate_view_setting(
        self,
        definition: ast.OperationDefinition,
        statement: ast.ViewSettingStatement,
        views: scope_tracker.ScopeTracker[
            ast.InterfaceViewDefinition | ast.LocalViewDefinition
        ],
        view_setting_order: view_setting_order_tracker.ViewSettingOrderTracker,
    ):
        """Validate a View Setting Statement in `definition`, and record it in `view_setting_order`."""
        target = statement.target
        source = statement.source
        target_ok = self._validate_looked_at_view(target, views)
        source_ok = self._validate_looked_at_view(source, views)
        if source_ok:
            self._diagnostics.extend(view_setting_order.check_source(source))
        if not target_ok:
            return
        view_setting_order.record_target(target)
        if source_ok and target.full_typed_name == source.full_typed_name:
            self._diagnostics.append(
                diagnostics.ViewSettingSameViewDiagnostic(
                    location=source.location, view_name=source.source_typed_name
                )
            )
            return
        target_view = views.get_definition(target)
        if isinstance(target_view, ast.InterfaceViewDefinition):
            if not target_view.is_output:
                self._diagnostics.append(
                    diagnostics.ViewSettingInputOnlyTargetDiagnostic(
                        location=target.location, view_name=target.source_typed_name
                    )
                )
            elif not target_view.is_input:
                self._diagnostics.append(
                    diagnostics.ViewSettingOutputOnlyTargetDiagnostic(
                        location=target.location, view_name=target.source_typed_name
                    )
                )
        if not source_ok:
            return
        source_view = views.get_definition(source)
        if (
            isinstance(target_view, ast.InterfaceViewDefinition)
            and target_view.is_input
            and target_view.is_output
            and not isinstance(source_view, ast.LocalViewDefinition)
        ):
            self._diagnostics.append(
                diagnostics.ViewSettingReadWriteTargetSourceNotLocalDiagnostic(
                    location=source.location,
                    target_name=target.source_typed_name,
                    source_name=source.source_typed_name,
                )
            )
        self._check_view_setting_qualities(
            definition, statement, target_view, source_view
        )
        if isinstance(target_view, ast.LocalViewDefinition):
            view_setting_order.require_execution_after(statement)

    def _check_view_setting_qualities(
        self,
        definition: ast.OperationDefinition,
        statement: ast.ViewSettingStatement,
        target_view: ast.InterfaceViewDefinition | ast.LocalViewDefinition,
        source_view: ast.InterfaceViewDefinition | ast.LocalViewDefinition,
    ):
        """Report a View Setting Statement whose views have different value qualities, or different encodings in an Encoding Operation."""
        target = statement.target
        source = statement.source
        if isinstance(definition, ast.EncodingOperationDefinition):
            target_encoding = target_view.quality_assignment_block.encoding
            source_encoding = source_view.quality_assignment_block.encoding
            # A view without an encoding is reported where it is defined.
            if (
                target_encoding is not None
                and source_encoding is not None
                and target_encoding.full_typed_name != source_encoding.full_typed_name
            ):
                self._diagnostics.append(
                    diagnostics.ViewSettingEncodingMismatchDiagnostic(
                        location=statement.location,
                        target_view=target.source_typed_name,
                        source_view=source.source_typed_name,
                        target_encoding=target_encoding.source_typed_name,
                        source_encoding=source_encoding.source_typed_name,
                    )
                )
            return
        target_value_quality = target_view.quality_assignment_block.value_quality
        source_value_quality = source_view.quality_assignment_block.value_quality
        # A view without a value quality is reported where it is defined.
        if (
            target_value_quality is not None
            and source_value_quality is not None
            and target_value_quality.full_typed_name
            != source_value_quality.full_typed_name
        ):
            self._diagnostics.append(
                diagnostics.ViewSettingValueQualityMismatchDiagnostic(
                    location=statement.location,
                    target_view=target.source_typed_name,
                    source_view=source.source_typed_name,
                    target_value_quality=target_value_quality.source_typed_name,
                    source_value_quality=source_value_quality.source_typed_name,
                )
            )

    def _validate_view_definition(
        self,
        definition: ast.OperationDefinition,
        view: ast.InterfaceViewDefinition | ast.LocalViewDefinition,
        views: scope_tracker.ScopeTracker[
            ast.InterfaceViewDefinition | ast.LocalViewDefinition
        ],
    ):
        if self._validate_view_name(view, views):
            self._unreferenced_views[view.typed_name] = view
        if isinstance(view, ast.LocalViewDefinition) and isinstance(
            definition, ast.EncodingOperationDefinition
        ):
            self._validate_encoding_operation_local_view_qualities(view)
            return
        statements: list[ast.QualityAssignmentStatement] = []
        quality_name_types: set[name_types.NameType] = set()
        for statement in view.quality_assignment_block.statements:
            quality = statement.typed_global_name
            if (
                isinstance(view, ast.LocalViewDefinition)
                and quality.name_type != name_types.NameType.VALUE
            ):
                self._diagnostics.append(
                    diagnostics.LocalViewNonValueQualityDiagnostic(
                        location=quality.location,
                        quality_name=quality.source_typed_name,
                    )
                )
                continue
            if quality.name_type in {
                name_types.NameType.POSITION,
                name_types.NameType.ACTION,
            }:
                self._diagnostics.append(
                    diagnostics.ViewPositionOrActionQualityDiagnostic(
                        location=quality.location,
                        quality_name=quality.source_typed_name,
                    )
                )
                continue
            if (
                isinstance(definition, ast.EncodingOperationDefinition)
                and quality.name_type == name_types.NameType.VALUE
            ):
                self._diagnostics.append(
                    diagnostics.EncodingOperationViewValueQualityDiagnostic(
                        location=quality.location,
                        quality_name=quality.source_typed_name,
                    )
                )
                continue
            if (
                isinstance(definition, ast.ValueOperationDefinition)
                and quality.name_type == name_types.NameType.ENCODING
            ):
                self._diagnostics.append(
                    diagnostics.ValueOperationViewEncodingDiagnostic(
                        location=quality.location,
                        quality_name=quality.source_typed_name,
                    )
                )
                continue
            quality_name_types.add(quality.name_type)
            statements.append(statement)
        self._validate_quality_assignment_statements(
            statements,
            multiple_values_diagnostic=diagnostics.ViewMultipleValueQualitiesDiagnostic,
        )
        if isinstance(definition, ast.EncodingOperationDefinition):
            if name_types.NameType.ENCODING not in quality_name_types:
                self._diagnostics.append(
                    diagnostics.ViewMissingEncodingDiagnostic(
                        location=view.typed_name.location,
                        view_name=view.typed_name.source_typed_name,
                    )
                )
            return
        if name_types.NameType.VALUE in quality_name_types:
            return
        if isinstance(view, ast.LocalViewDefinition):
            self._diagnostics.append(
                diagnostics.LocalViewMissingValueQualityDiagnostic(
                    location=view.typed_name.location,
                    view_name=view.typed_name.source_typed_name,
                )
            )
            return
        self._diagnostics.append(
            diagnostics.ViewMissingValueQualityDiagnostic(
                location=view.typed_name.location,
                view_name=view.typed_name.source_typed_name,
            )
        )

    def _validate_encoding_operation_local_view_qualities(
        self, view: ast.LocalViewDefinition
    ):
        """Validate that a local view in an Encoding Operation is assigned exactly one encoding and nothing else."""
        statements: list[ast.QualityAssignmentStatement] = []
        first_encoding: ast.GlobalTypedNameReference | None = None
        for statement in view.quality_assignment_block.statements:
            quality = statement.typed_global_name
            if quality.name_type != name_types.NameType.ENCODING:
                self._diagnostics.append(
                    diagnostics.LocalViewNonEncodingDiagnostic(
                        location=quality.location,
                        quality_name=quality.source_typed_name,
                    )
                )
                continue
            # A repeated encoding is reported as a duplicate quality
            # assignment.
            if (
                first_encoding is not None
                and quality.full_typed_name != first_encoding.full_typed_name
            ):
                self._diagnostics.append(
                    diagnostics.LocalViewMultipleEncodingsDiagnostic(
                        location=quality.location,
                        first_encoding_name=first_encoding.source_typed_name,
                        first_assignment_line=first_encoding.location.line,
                    )
                )
                continue
            if first_encoding is None:
                first_encoding = quality
            statements.append(statement)
        # The block has only encodings left, so no multiple value qualities
        # are reported.
        self._validate_quality_assignment_statements(
            statements,
            multiple_values_diagnostic=diagnostics.ViewMultipleValueQualitiesDiagnostic,
        )
        if first_encoding is None:
            self._diagnostics.append(
                diagnostics.LocalViewMissingEncodingDiagnostic(
                    location=view.typed_name.location,
                    view_name=view.typed_name.source_typed_name,
                )
            )

    def _validate_logical_operation_definition(
        self, definition: ast.LogicalOperationDefinition
    ):
        views = scope_tracker.ScopeTracker[ast.LogicalOperationViewDefinition]()
        has_output_view = False
        for view in definition.views:
            _ = self._validate_view_name(view, views)
            has_output_view = has_output_view or view.is_output
        if not has_output_view:
            self._diagnostics.append(
                diagnostics.LogicalOperationWithoutOutputViewDiagnostic(
                    location=definition.typed_name.location
                )
            )

    def _validate_logical_operation_support_statements(
        self, statements: Sequence[ast.LogicalOperationSupportStatement]
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        greatest_name: str | None = None
        for statement in statements:
            logical_operation = statement.logical_operation
            reference_diagnostics = self._typed_name_diagnostics(logical_operation)
            self._diagnostics.extend(reference_diagnostics)
            if reference_diagnostics:
                continue
            first_line = seen_lines.get(logical_operation)
            if first_line is not None:
                self._diagnostics.append(
                    diagnostics.DuplicateLogicalOperationSupportDiagnostic(
                        location=logical_operation.location,
                        logical_operation_name=logical_operation.source_typed_name,
                        first_support_line=first_line,
                    )
                )
                continue
            seen_lines[logical_operation] = logical_operation.location.line
            # Comparing full typed names keeps the order the same whether or
            # not a reference is written in short form.
            name = logical_operation.full_typed_name
            if greatest_name is not None and name < greatest_name:
                self._diagnostics.append(
                    diagnostics.LogicalOperationSupportOrderDiagnostic(
                        location=logical_operation.location,
                        logical_operation_name=name,
                        logical_operation_name_it_must_precede=greatest_name,
                    )
                )
            else:
                greatest_name = name
            self._process_reference(logical_operation)

    def _validate_view_name[ViewT: ast.ViewDefinition | ast.LocalViewDefinition](
        self,
        view: ViewT,
        views: scope_tracker.ScopeTracker[ViewT],
    ) -> bool:
        """Validate the name of a view and add it to the scope if no earlier view has its name.

        Returns whether it was added.
        """
        self._diagnostics.extend(
            name_validators.validate_local_name_format(view.typed_name.name_content)
        )
        if views.is_defined(view.typed_name):
            self._diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    location=view.typed_name.location,
                    local_name=view.typed_name.name_content.name,
                    first_definition_line=views.defined_on_line(view.typed_name),
                )
            )
            return False
        views.add_definition(view)
        return True

    def _validate_execution[
        LookedAt: (ast.PositionReference, ast.LocalTypedNameReference)
    ](
        self,
        executed: ast.GlobalTypedNameReference,
        arguments: Sequence[ast.OperationArgumentStatement[LookedAt | ast.Literal]],
        validate_looked_at: Callable[[LookedAt], bool],
    ) -> bool:
        """Validate an Operation Execution Statement or a Logical Operation Execution Statement, and return whether the executed name is valid.

        validate_looked_at validates a looked-at position or view and returns
        whether it is valid to check for aliasing.
        """
        executed_diagnostics = self._typed_name_diagnostics(executed)
        self._diagnostics.extend(executed_diagnostics)
        if not executed_diagnostics:
            self._process_reference(executed)
        self._validate_operation_arguments(arguments, validate_looked_at)
        return not executed_diagnostics

    def _validate_operation_arguments[
        LookedAt: (ast.PositionReference, ast.LocalTypedNameReference)
    ](
        self,
        arguments: Sequence[ast.OperationArgumentStatement[LookedAt | ast.Literal]],
        validate_looked_at: Callable[[LookedAt], bool],
    ):
        looked_at_lines: dict[str, int] = {}
        argument_lines: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, int
        ] = typed_name_dict.TypedNameDict()
        for argument in arguments:
            view_name_diagnostics = name_validators.validate_local_name_format(
                argument.view.name_content
            )
            self._diagnostics.extend(view_name_diagnostics)
            if not view_name_diagnostics:
                self._check_duplicate_argument(argument.view, argument_lines)
            looking_at = argument.looking_at
            if isinstance(looking_at, ast.Literal):
                _ = self._validate_literal(looking_at)
                continue
            if not validate_looked_at(looking_at):
                continue
            match looking_at:
                case ast.PositionReference():
                    canonical_name = looking_at.canonical_chained_name
                    source_name = looking_at.source_chained_name
                case ast.LocalTypedNameReference():
                    canonical_name = looking_at.full_typed_name
                    source_name = looking_at.source_typed_name
            first_line = looked_at_lines.get(canonical_name)
            if first_line is None:
                looked_at_lines[canonical_name] = looking_at.location.line
            else:
                self._diagnostics.append(
                    diagnostics.AliasedViewDiagnostic(
                        location=looking_at.location,
                        looked_at_name=source_name,
                        first_argument_line=first_line,
                    )
                )

    def _validate_looked_at_in_action(
        self,
        looking_at: ast.PositionReference,
        scope: scope_tracker.PositionScopeTracker,
    ) -> bool:
        position_ok = self._validate_full_chained_name(looking_at, scope)
        self._looked_at_position_validity.append(position_ok)
        return position_ok

    def _check_duplicate_argument(
        self,
        view: ast.LocalTypedNameReference,
        argument_lines: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int],
    ):
        first_line = argument_lines.get(view)
        if first_line is not None:
            self._diagnostics.append(
                diagnostics.DuplicateOperationArgumentDiagnostic(
                    location=view.location,
                    view_name=view.source_typed_name,
                    first_argument_line=first_line,
                )
            )
            return
        argument_lines[view] = view.location.line

    def _validate_looked_at_view(
        self,
        view: ast.LocalTypedNameReference,
        views: scope_tracker.ScopeTracker[
            ast.InterfaceViewDefinition | ast.LocalViewDefinition
        ],
    ) -> bool:
        name_diagnostics = name_validators.validate_local_name_format(view.name_content)
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return False
        if not views.is_defined(view):
            self._diagnostics.append(
                diagnostics.UndefinedLocalNameDiagnostic(
                    location=view.location,
                    local_name=view.full_typed_name,
                )
            )
            return False
        if view in self._unreferenced_views:
            del self._unreferenced_views[view]
        return True

    def _validate_trigger_conditions(
        self,
        trigger_conditions: ast.TriggerConditionsBlock,
        scope: scope_tracker.PositionScopeTracker,
    ):
        condition = trigger_conditions.condition
        if isinstance(condition, ast.PositionPresenceStatement):
            _ = self._validate_full_chained_name(condition.position_reference, scope)

    def _validate_action_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.PositionScopeTracker,
    ):
        if not action_statements.statements:
            self._diagnostics.append(
                diagnostics.EmptyActionStatementsBlockDiagnostic(
                    location=action_statements.location,
                )
            )
        for stmt in action_statements.statements:
            match stmt:
                case ast.ValueSettingStatement():
                    self._validate_value_setting(stmt, scope)
                case ast.LocalPositionDefinition():
                    self._validate_local_position_definition(stmt, scope)
                case ast.CreateParticleStatement():
                    self._validate_create_particle(stmt, scope)
                case ast.MoveParticleStatement():
                    self._validate_move_particle(stmt, scope)
                case ast.DestroyParticleStatement():
                    self._validate_destroy_particle(stmt, scope)
                case ast.OperationExecutionStatement():
                    _ = self._validate_execution(
                        stmt.operation,
                        stmt.arguments,
                        lambda looking_at: self._validate_looked_at_in_action(
                            looking_at, scope
                        ),
                    )

    def _validate_value_setting(
        self,
        stmt: ast.ValueSettingStatement,
        scope: scope_tracker.PositionScopeTracker,
    ):
        target_ok = self._validate_full_chained_name(stmt.target_position, scope)
        match stmt.source:
            case ast.Literal():
                source_ok = self._validate_literal(stmt.source)
            case ast.PositionReference():
                source_ok = self._validate_full_chained_name(stmt.source, scope)
                if (
                    stmt.target_position.canonical_chained_name_tuple
                    == stmt.source.canonical_chained_name_tuple
                ):
                    self._diagnostics.append(
                        diagnostics.ValueSettingSamePositionDiagnostic(
                            location=stmt.source.location,
                            position_name=stmt.source.source_chained_name,
                        )
                    )
        self._particle_statement_validity.append(
            validation_result.ParticleStatementValidity(
                target_ok=target_ok, source_ok=source_ok
            )
        )

    def _validate_literal(self, literal: ast.Literal) -> bool:
        """Validate a literal's Potential Literal name and return whether it is valid."""
        potential_literal = literal.potential_literal
        name_diagnostics = self._typed_name_diagnostics(potential_literal)
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return False
        self._process_reference(potential_literal)
        return True

    def _validate_local_position_definition(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.PositionScopeTracker,
    ):
        self._validate_local_name_format_and_conflicts(local_def, scope)
        self._validate_quality_assignment_block(local_def.quality_assignment_block)

    def _validate_quality_assignment_block(
        self, block: ast.QualityAssignmentBlock | None
    ):
        if block is not None:
            self._validate_quality_assignment_statements(
                block.statements,
                multiple_values_diagnostic=diagnostics.PositionMultipleValueQualitiesDiagnostic,
            )

    def _validate_local_name_format_and_conflicts(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.PositionScopeTracker,
    ):
        self._diagnostics.extend(
            name_validators.validate_local_name_format(
                local_def.typed_name.name_content
            )
        )
        name = local_def.typed_name.name_content.name
        if scope.is_defined(local_def.typed_name):
            self._diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    location=local_def.typed_name.location,
                    local_name=name,
                    first_definition_line=scope.defined_on_line(local_def.typed_name),
                )
            )
            return
        scope.add_definition(local_def)
        self._unreferenced_positions[local_def.typed_name] = local_def

    def _validate_create_particle(
        self,
        stmt: ast.CreateParticleStatement,
        scope: scope_tracker.PositionScopeTracker,
    ):
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
        )
        self._particle_statement_validity.append(
            validation_result.ParticleStatementValidity(
                target_ok=target_ok,
            )
        )

    def _validate_move_particle(
        self,
        stmt: ast.MoveParticleStatement,
        scope: scope_tracker.PositionScopeTracker,
    ):
        source_ok = self._validate_full_chained_name(
            stmt.source_position,
            scope,
        )
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
        )
        from_is_prefix_of_to = self._check_if_from_is_a_prefix_of_to(stmt)
        self._particle_statement_validity.append(
            validation_result.ParticleStatementValidity(
                source_ok=source_ok,
                target_ok=target_ok,
                from_is_prefix_of_to=from_is_prefix_of_to,
            )
        )

    def _check_if_from_is_a_prefix_of_to(
        self,
        stmt: ast.MoveParticleStatement,
    ) -> bool:
        """Check if the from chain is a prefix of the to chain, and emit a diagnostic if so.

        Also emits a diagnostic if the from and to chains are identical.
        """
        from_pos = stmt.source_position
        to_pos = stmt.target_position
        if len(from_pos.typed_names) > len(to_pos.typed_names):
            return False
        for from_name, to_name in zip(
            from_pos.typed_names, to_pos.typed_names, strict=False
        ):
            if from_name.full_typed_name != to_name.full_typed_name:
                return False

        if len(from_pos.typed_names) == len(to_pos.typed_names):
            self._diagnostics.append(
                diagnostics.MoveToSamePositionDiagnostic(
                    location=to_pos.typed_names[-1].location,
                    position_name=to_pos.source_chained_name,
                )
            )
            return False

        divergence = to_pos.typed_names[len(from_pos.typed_names)]
        self._diagnostics.append(
            diagnostics.MoveIntoDefiningPositionDiagnostic(
                location=divergence.location,
                source_position=from_pos.source_chained_name,
                target_position=to_pos.source_chained_name,
            )
        )
        return True

    def _validate_destroy_particle(
        self,
        stmt: ast.DestroyParticleStatement,
        scope: scope_tracker.PositionScopeTracker,
    ):
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
        )
        self._particle_statement_validity.append(
            validation_result.ParticleStatementValidity(
                target_ok=target_ok,
            )
        )

    def _validate_full_chained_name(
        self,
        chain: ast.ChainedName,
        scope: scope_tracker.PositionScopeTracker,
    ) -> bool:
        """Validate a full chained name reference.

        Returns whether the caller may continue processing this reference.
        """
        first = chain.typed_names[0]
        last_typed_name = chain.typed_names[-1]
        may_continue = True

        if ast.is_local_reference(first) and first in self._unreferenced_positions:
            del self._unreferenced_positions[first]

        is_self_reference = (
            first.full_typed_name == self._definition.typed_name.source_typed_name
        )
        is_chained_self_reference = is_self_reference and len(chain.typed_names) > 1
        if is_chained_self_reference:
            self._diagnostics.append(
                diagnostics.UnnecessarySelfReferenceDiagnostic(
                    location=first.location,
                    definition_name=self._definition.typed_name.source_typed_name,
                )
            )
            return False

        if not scope.is_defined(first) and ast.is_local_reference(first):
            self._diagnostics.append(
                diagnostics.UndefinedLocalNameDiagnostic(
                    location=first.location,
                    local_name=first.full_typed_name,
                )
            )
            may_continue = False

        if not is_self_reference and ast.is_global_reference(first):
            if first in self._implied_qualities:
                self._used_implied_qualities.add(first.full_typed_name)
            else:
                self._diagnostics.append(
                    diagnostics.UnknownGlobalNameDiagnostic(
                        location=first.location,
                        source_global_name=first.source_typed_name,
                        full_global_name=first.full_typed_name,
                    )
                )
                may_continue = False

        previous_element = None
        for typed_name in chain.typed_names:
            self._validate_chained_name_element(typed_name)
            # Local names in chains may only come right after global action names.
            if (
                previous_element
                and ast.is_local_reference(typed_name)
                and not (
                    ast.is_global_reference(previous_element)
                    and previous_element.name_type == name_types.NameType.ACTION
                )
            ):
                self._diagnostics.append(
                    diagnostics.ChainedLocalNameRequiresActionDiagnostic(
                        location=typed_name.location,
                        local_name=typed_name.full_typed_name,
                        preceding_name=previous_element.full_typed_name,
                    )
                )
                # Don't even try to process this name; it will fail when we try to
                # resolve it in program_validator.
                may_continue = False
            previous_element = typed_name

        if last_typed_name.name_type != name_types.NameType.POSITION:
            self._diagnostics.append(
                diagnostics.PositionReferenceChainEndDiagnostic(
                    location=last_typed_name.location,
                )
            )
            may_continue = False

        return may_continue

    def _typed_name_diagnostics(
        self, typed_name: ast.TypedNameReference
    ) -> list[diagnostics.Diagnostic]:
        """Validate a typed name reference's format."""
        # A definition names the same few typed names many times. A name's
        # diagnostics depend only on its source text and on the definition,
        # so a name that was valid once is valid at every later site.
        source_typed_name = typed_name.source_typed_name
        if source_typed_name in self._valid_typed_names:
            return []
        name_diagnostics = name_validators.validate_typed_name(
            typed_name, self._definition
        )
        if not name_diagnostics:
            self._valid_typed_names.add(source_typed_name)
        return name_diagnostics

    def _validate_chained_name_element(
        self,
        chain_element: ast.TypedNameReference,
    ):
        """Validate a single chain element.

        Returns whether or not the name was valid.
        """
        name_diagnostics = self._typed_name_diagnostics(chain_element)
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return

        if ast.is_global_reference(chain_element):
            self._process_reference(chain_element)
        elif chain_element.name_type == name_types.NameType.ACTION:
            self._diagnostics.append(
                diagnostics.LocalActionNameDiagnostic(
                    location=chain_element.location,
                    local_name=chain_element.name_content.name,
                )
            )

    def _validate_quality_assignment_statements(
        self,
        statements: Sequence[ast.QualityAssignmentStatement],
        *,
        multiple_values_diagnostic: type[diagnostics.MultipleValueQualitiesDiagnostic],
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        first_value: ast.GlobalTypedNameReference | None = None
        for statement in statements:
            reference_diagnostics = self._typed_name_diagnostics(
                statement.typed_global_name
            )
            self._diagnostics.extend(reference_diagnostics)
            if reference_diagnostics:
                continue
            first_line = seen_lines.get(statement.typed_global_name)
            if first_line is not None:
                self._diagnostics.append(
                    diagnostics.DuplicateQualityAssignmentDiagnostic(
                        location=statement.typed_global_name.location,
                        quality_name=statement.typed_global_name.source_typed_name,
                        first_assignment_line=first_line,
                    )
                )
                continue
            seen_lines[statement.typed_global_name] = (
                statement.typed_global_name.location.line
            )
            if statement.typed_global_name.name_type == name_types.NameType.VALUE:
                if first_value is not None:
                    self._diagnostics.append(
                        multiple_values_diagnostic(
                            location=statement.typed_global_name.location,
                            first_value_name=first_value.source_typed_name,
                            first_assignment_line=first_value.location.line,
                        )
                    )
                    continue
                first_value = statement.typed_global_name
            self._process_reference(statement.typed_global_name)

    def _validate_quality_implications(
        self,
        implications: Iterable[ast.QualityImplicationStatement],
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        for implication in implications:
            name_diagnostics = self._typed_name_diagnostics(
                implication.typed_global_name
            )
            self._diagnostics.extend(name_diagnostics)
            if name_diagnostics:
                continue
            first_line = seen_lines.get(implication.typed_global_name)
            if first_line is not None:
                self._diagnostics.append(
                    diagnostics.DuplicateQualityImplicationDiagnostic(
                        location=implication.typed_global_name.location,
                        implication_name=implication.typed_global_name.source_typed_name,
                        first_implication_line=first_line,
                    )
                )
                continue
            seen_lines[implication.typed_global_name] = (
                implication.typed_global_name.location.line
            )
            self._implied_qualities[implication.typed_global_name] = implication
            self._process_reference(implication.typed_global_name)

    def _check_unreferenced_positions(self):
        for local_def in self._unreferenced_positions.values():
            self._diagnostics.append(
                diagnostics.UnreferencedPositionDiagnostic(
                    location=local_def.typed_name.location,
                    position_name=local_def.typed_name.source_typed_name,
                )
            )

    def _check_unused_quality_implications(self):
        for implied_name, implication in self._implied_qualities.items():
            if implied_name.full_typed_name in self._used_implied_qualities:
                continue
            self._diagnostics.append(
                diagnostics.UnusedQualityImplicationDiagnostic(
                    location=implication.typed_global_name.location,
                    implication_name=implication.typed_global_name.source_typed_name,
                )
            )

    def _process_reference(
        self,
        typed_global_name: ast.GlobalTypedNameReference,
    ):
        """Record a reference edge for a global name reference."""
        global_name = typed_global_name.name_content

        # Only the first reference site per target emits an edge; downstream
        # per-target diagnostics (missing file, cycle, wrong type) then fire
        # once per (definition, target) pair instead of once per source line.
        if typed_global_name.full_typed_name in self._seen_edge_targets:
            return
        self._seen_edge_targets.add(typed_global_name.full_typed_name)

        # Process a cross-FQUN reference in a filesystem context.
        if (
            global_name.fqun is not None
            and config.universe_needs_configuration(global_name.fqun.canonical)
            and self._context.is_filesystem_context
        ):
            root_config = self._context.root_config
            if root_config is None:
                raise ValueError("filesystem contexts must define a root config")
            fqun_string = global_name.fqun.canonical
            if fqun_string in self._unknown_fquns:
                return
            if fqun_string not in root_config.sub_roots:
                self._unknown_fquns.add(fqun_string)
                self._diagnostics.append(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        location=global_name.fqun.location,
                        universe=fqun_string,
                        current_universe_name=root_config.fqun,
                    )
                )
                return

        self._reference_edges.append(
            reference_graph.ReferenceEdge(
                enclosing_definition=self._definition,
                global_name_reference=typed_global_name,
            )
        )
