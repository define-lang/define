"""Pure per-file validation for the Define language.

FileStructuralValidator is a stateless worker that processes one file at a time.
It takes immutable inputs and produces immutable outputs, with no access
to shared mutable state.
"""

from __future__ import annotations

import pathlib
from functools import cached_property
from typing import TYPE_CHECKING

import msgspec

from define.compiler import (
    ast,
    config,
    constants,
    diagnostics,
    exceptions,
    parser,
    parser_error_classification,
)
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.graphs import reference_graph
from define.compiler.validator import scope_tracker, stats, validation_result
from define.compiler.validator.structural import name_validators

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class FileValidationContext(msgspec.Struct, frozen=True, dict=True):
    """Immutable input for validating a single file."""

    file_path: define_path.DefinePath
    root_prefix: define_path.DefinePath
    root_config: config.ProjectRootConfig | None = None
    is_filesystem_context: bool = True

    @cached_property
    def full_path(self) -> define_path.DefinePath:
        """Return full filesystem path for this validation context."""
        return self.root_prefix / self.file_path

    @cached_property
    def expected_definition_path(self) -> define_path.DefinePath | None:
        """Return the expected definition path for filesystem-backed validation."""
        return self.file_path.without_suffix(constants.DEFINE_FILE_SUFFIX)


class EmptyFileValidationContext(FileValidationContext, frozen=True, dict=True):
    """Validation context for non-filesystem source validation."""

    file_path: define_path.DefinePath = constants.NON_FILESYSTEM_PATH
    root_prefix: define_path.DefinePath = define_path.EMPTY
    root_config: config.ProjectRootConfig | None = None
    is_filesystem_context: bool = False

    @cached_property
    def expected_definition_path(self) -> define_path.DefinePath | None:
        """Return no expected definition path for source-only validation."""
        return None


class FileStructuralValidator:
    """Stateless per-file validator.

    Processes one file: reads from disk, parses, transforms, and validates
    local rules. Produces a FileValidationResult with reference edges for
    the coordinator to process.
    """

    _parser: parser.Parser

    def __init__(self, lark_parser: parser.Parser):
        """Initialize with a shared parser instance."""
        self._parser = lark_parser

    def validate_file(
        self, context: FileValidationContext
    ) -> validation_result.FileValidationResult:
        """Validate a single file and return the result."""
        tracker = stats.ValidationStatsTracker()

        source, load_error = self._load_file(context.full_path)
        tracker.mark_file_loading_finished()
        if load_error is not None:
            return validation_result.FileValidationResult(
                exception=load_error,
                source_lines=None,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
                file_diagnostics=[],
                definition_results=[],
            )
        return self._validate_source(
            context=context,
            source=source,
            tracker=tracker,
        )

    def validate_source(
        self,
        source: str,
    ) -> validation_result.FileValidationResult:
        """Validate source text without loading from the filesystem."""
        context = EmptyFileValidationContext()
        tracker = stats.ValidationStatsTracker()
        tracker.mark_file_loading_finished()
        return self._validate_source(
            context=context,
            source=source,
            tracker=tracker,
        )

    def _validate_source(
        self,
        context: FileValidationContext,
        source: str,
        tracker: stats.ValidationStatsTracker,
    ) -> validation_result.FileValidationResult:
        """Parse, transform, and validate source text."""
        parser_file_path = (
            context.full_path.as_posix_path() if context.is_filesystem_context else None
        )
        parse_result = self._parser.parse_and_transform(
            source, file_path=parser_file_path
        )
        tracker.mark_parse_finished()

        if parse_result.exception is not None:
            indentation_diags: list[diagnostics.Diagnostic] = (
                parse_result.diagnostics if context.is_filesystem_context else []
            )
            return validation_result.FileValidationResult(
                exception=parse_result.exception,
                source_lines=source.splitlines(),
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
                file_diagnostics=indentation_diags,
                definition_results=[],
            )

        if parse_result.program is None:
            raise ValueError("parse produced no program despite reporting no exception")
        program = parse_result.program

        seen_definitions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedNameInDefinition, ast.GlobalDefinition
        ] = typed_name_dict.TypedNameDict()
        definition_results: list[validation_result.DefinitionValidationResult] = []
        for definition in program.definitions:
            result = DefinitionStructuralValidator(
                definition=definition,
                context=context,
                seen_definitions=seen_definitions,
            ).validate_definition()
            definition_results.append(result)
            if definition.typed_name not in seen_definitions:
                seen_definitions[definition.typed_name] = definition
        tracker.mark_file_validation_finished()

        return validation_result.FileValidationResult(
            exception=None,
            source_lines=source.splitlines(),
            file_path=context.full_path,
            root_prefix=context.root_prefix,
            stats=tracker.build(),
            file_diagnostics=parse_result.diagnostics
            if context.is_filesystem_context
            else [],
            definition_results=definition_results,
        )

    def _load_file(
        self,
        path: define_path.DefinePath,
    ) -> tuple[str, validation_result.AnyValidationException | None]:
        """Load a Define source file and return source and syntax errors."""
        posix_path = path.as_posix_path()
        try:
            raw = pathlib.Path(posix_path).read_bytes()
        except FileNotFoundError:
            return "", exceptions.SourceFileNotFoundError(
                filesystem_path=pathlib.Path(posix_path)
            )
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            return "", parser_error_classification.make_invalid_encoding_error(
                raw, e, posix_path
            )
        return source, None


class DefinitionStructuralValidator:
    """Validates one definition within a single file.

    Is mutable and not thread-safe.
    """

    _context: FileValidationContext
    _diagnostics: list[diagnostics.Diagnostic]
    _definition: ast.GlobalDefinition
    _reference_edges: list[reference_graph.ReferenceEdge]
    _seen_edge_targets: set[str]
    _particle_statement_validity: list[validation_result.ParticleStatementValidity]
    _looked_at_position_validity: list[bool]
    _seen_definitions: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameInDefinition, ast.GlobalDefinition
    ]
    _unknown_fquns: set[str]
    _implied_qualities: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameReference, ast.QualityImplicationStatement
    ]
    _used_implied_qualities: set[str]
    _unreferenced_positions: typed_name_dict.TypedNameDict[
        ast.LocalTypedNameReference, ast.LocalPositionDefinition
    ]

    def __init__(
        self,
        definition: ast.GlobalDefinition,
        context: FileValidationContext,
        seen_definitions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedNameInDefinition, ast.GlobalDefinition
        ],
    ):
        """Initialize per-definition validation state from file-level state."""
        self._definition = definition
        self._context = context
        self._diagnostics = []
        self._reference_edges = []
        self._seen_edge_targets = set()
        self._particle_statement_validity = []
        self._looked_at_position_validity = []
        self._seen_definitions = seen_definitions
        self._unknown_fquns = set()
        self._implied_qualities = typed_name_dict.TypedNameDict()
        self._used_implied_qualities = set()
        self._unreferenced_positions = typed_name_dict.TypedNameDict()

    def validate_definition(self) -> validation_result.DefinitionValidationResult:
        """Validate one top-level definition and return its validation result."""
        self._diagnostics.extend(
            name_validators.validate_global_name(
                self._definition.typed_name.name_content
            )
        )
        self._validate_path_matches_file()
        self._validate_fqun_matches_expected()
        self._validate_not_duplicate_in_file()

        match self._definition:
            case ast.ActionDefinition():
                self._validate_action_definition(self._definition)
            case ast.PositionDefinition():
                self._validate_global_position_definition_block(self._definition)
            case ast.PotentialLiteralDefinition():
                encoding = self._definition.encoding
                encoding_diagnostics = name_validators.validate_typed_name(
                    encoding, self._definition
                )
                self._diagnostics.extend(encoding_diagnostics)
                if not encoding_diagnostics:
                    self._process_reference(encoding)
            case ast.OperationDefinition():
                self._validate_operation_definition(self._definition)
            case _:
                pass
        return self.build_result()

    def build_result(self) -> validation_result.DefinitionValidationResult:
        """Build a result object from the validator's private state."""
        return validation_result.DefinitionValidationResult(
            definition=self._definition,
            _diagnostics=self._diagnostics,
            reference_edges=self._reference_edges,
            particle_statement_validity=self._particle_statement_validity,
            looked_at_position_validity=self._looked_at_position_validity,
        )

    def _validate_path_matches_file(self):
        if self._context.expected_definition_path is None:
            return
        definition_path = self._definition.typed_name.name_content.path.name
        expected_path = str(self._context.expected_definition_path.as_absolute_path())
        if definition_path != expected_path:
            self._diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    location=self._definition.typed_name.name_content.path.location,
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_fqun_matches_expected(self):
        root_config = self._context.root_config
        expected_fqun = "" if root_config is None else root_config.fqun
        if not expected_fqun:
            return
        actual = self._definition.typed_name.name_content.fqun.canonical
        if actual != expected_fqun:
            self._diagnostics.append(
                diagnostics.FqunMismatchDiagnostic(
                    location=self._definition.typed_name.name_content.fqun.location,
                    expected=expected_fqun,
                    actual=actual,
                )
            )

    def _validate_not_duplicate_in_file(self):
        """Check for within-file duplicates."""
        if self._definition.typed_name in self._seen_definitions:
            first_def = self._seen_definitions[self._definition.typed_name]
            self._diagnostics.append(
                diagnostics.DuplicateDefinitionDiagnostic(
                    location=self._definition.location,
                    definition_type=self._definition.typed_name.name_type.value,
                    path=self._definition.typed_name.name_content.path.name,
                    first_definition_line=first_def.location.line,
                )
            )

    def _validate_action_definition(
        self,
        definition: ast.ActionDefinition,
    ):
        self._validate_quality_implications(definition.quality_implications)
        scope = scope_tracker.ScopeTracker()
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

    def _validate_global_position_definition_block(
        self,
        definition: ast.PositionDefinition,
    ):
        self._validate_quality_implications(definition.quality_implications)
        if definition.constraints:
            self._validate_position_requirements(
                definition.constraints.requirements,
                multiple_values_diagnostic=diagnostics.PositionMultipleValueConstraintsDiagnostic,
            )
        self._check_unreferenced_positions()
        self._check_unused_quality_implications()

    def _validate_operation_definition(self, definition: ast.OperationDefinition):
        views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ] = typed_name_dict.TypedNameDict()
        unreferenced_views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ] = typed_name_dict.TypedNameDict()
        for view in definition.views:
            self._validate_view_definition(definition, view, views, unreferenced_views)
        executes_all_views = False
        for statement in definition.operation_statements:
            match statement:
                case ast.OperationExecutionStatement():
                    self._validate_operation_execution(
                        statement,
                        lambda looking_at: self._validate_looked_at_in_operation(
                            looking_at, views, unreferenced_views
                        ),
                    )
                case (
                    ast.EncodingOperationExecutionStatement()
                    | ast.ComputerOperationExecutionStatement()
                ):
                    executes_all_views = True
        # The encoding operation or computer operation receives every interface
        # view, so executing it references all of them.
        if executes_all_views:
            return
        for view in unreferenced_views.values():
            self._diagnostics.append(
                diagnostics.UnreferencedViewDiagnostic(
                    location=view.typed_name.name_content.location,
                    view_name=view.typed_name.source_typed_name,
                    operation_name_type=definition.typed_name.name_type,
                )
            )

    def _validate_view_definition(
        self,
        definition: ast.OperationDefinition,
        view: ast.ViewDefinition,
        views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
        unreferenced_views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
    ):
        self._diagnostics.extend(
            name_validators.validate_local_name_format(view.typed_name.name_content)
        )
        if view.typed_name in views:
            self._diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    location=view.typed_name.name_content.location,
                    local_name=view.typed_name.name_content.name,
                    first_definition_line=views[view.typed_name].location.line,
                )
            )
        else:
            views[view.typed_name] = view
            unreferenced_views[view.typed_name] = view
        requirements: list[ast.PositionRequirementStatement] = []
        constraint_types: set[ast.NameType] = set()
        for requirement in view.constraints.requirements:
            constraint = requirement.typed_global_name
            if constraint.name_type in (ast.NameType.POSITION, ast.NameType.ACTION):
                self._diagnostics.append(
                    diagnostics.ViewQualityConstraintDiagnostic(
                        location=constraint.location,
                        constraint_name=constraint.source_typed_name,
                    )
                )
                continue
            if (
                isinstance(definition, ast.EncodingOperationDefinition)
                and constraint.name_type == ast.NameType.VALUE
            ):
                self._diagnostics.append(
                    diagnostics.EncodingOperationViewValueConstraintDiagnostic(
                        location=constraint.location,
                        constraint_name=constraint.source_typed_name,
                    )
                )
                continue
            if (
                isinstance(definition, ast.ValueOperationDefinition)
                and constraint.name_type == ast.NameType.ENCODING
            ):
                self._diagnostics.append(
                    diagnostics.ValueOperationViewEncodingConstraintDiagnostic(
                        location=constraint.location,
                        constraint_name=constraint.source_typed_name,
                    )
                )
                continue
            constraint_types.add(constraint.name_type)
            requirements.append(requirement)
        self._validate_position_requirements(
            requirements,
            multiple_values_diagnostic=diagnostics.ViewMultipleValueConstraintsDiagnostic,
        )
        if isinstance(definition, ast.EncodingOperationDefinition):
            if ast.NameType.ENCODING not in constraint_types:
                self._diagnostics.append(
                    diagnostics.ViewMissingEncodingConstraintDiagnostic(
                        location=view.typed_name.name_content.location,
                        view_name=view.typed_name.source_typed_name,
                    )
                )
        elif ast.NameType.VALUE not in constraint_types:
            self._diagnostics.append(
                diagnostics.ViewMissingValueConstraintDiagnostic(
                    location=view.typed_name.name_content.location,
                    view_name=view.typed_name.source_typed_name,
                )
            )

    def _validate_operation_execution(
        self,
        statement: ast.OperationExecutionStatement,
        validate_looked_at: Callable[
            [ast.PositionReference | ast.LocalTypedNameReference], bool
        ],
    ):
        """Validate an Operation Execution Statement.

        validate_looked_at validates a looked-at position or view and returns
        whether it is valid to check for aliasing.
        """
        operation_diagnostics = name_validators.validate_typed_name(
            statement.operation, self._definition
        )
        self._diagnostics.extend(operation_diagnostics)
        if not operation_diagnostics:
            self._process_reference(statement.operation)
        self._validate_operation_arguments(statement.arguments, validate_looked_at)

    def _validate_operation_arguments(
        self,
        arguments: Sequence[ast.OperationArgumentStatement],
        validate_looked_at: Callable[
            [ast.PositionReference | ast.LocalTypedNameReference], bool
        ],
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

    def _validate_looked_at_in_operation(
        self,
        looking_at: ast.PositionReference | ast.LocalTypedNameReference,
        views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
        unreferenced_views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
    ) -> bool:
        match looking_at:
            case ast.LocalTypedNameReference():
                return self._validate_looked_at_view(
                    looking_at, views, unreferenced_views
                )
            case ast.PositionReference():
                self._diagnostics.append(
                    diagnostics.OperationArgumentPositionDiagnostic(
                        location=looking_at.location,
                        position_name=looking_at.source_chained_name,
                    )
                )
                return False

    def _validate_looked_at_in_action(
        self,
        looking_at: ast.PositionReference | ast.LocalTypedNameReference,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        match looking_at:
            case ast.PositionReference():
                position_ok = self._validate_full_chained_name(looking_at, scope)
                self._looked_at_position_validity.append(position_ok)
                return position_ok
            case ast.LocalTypedNameReference():
                self._diagnostics.append(
                    diagnostics.OperationArgumentViewDiagnostic(
                        location=looking_at.location,
                        view_name=looking_at.source_typed_name,
                    )
                )
                return False

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
        views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
        unreferenced_views: typed_name_dict.TypedNameDict[
            ast.LocalTypedNameReference, ast.ViewDefinition
        ],
    ) -> bool:
        name_diagnostics = name_validators.validate_local_name_format(view.name_content)
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return False
        if view not in views:
            self._diagnostics.append(
                diagnostics.UndefinedLocalNameDiagnostic(
                    location=view.location,
                    local_name=view.full_typed_name,
                )
            )
            return False
        if view in unreferenced_views:
            del unreferenced_views[view]
        return True

    def _validate_trigger_conditions(
        self,
        trigger_conditions: ast.TriggerConditionsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        condition = trigger_conditions.condition
        if isinstance(condition, ast.PositionPresenceStatement):
            _ = self._validate_full_chained_name(condition.position_reference, scope)

    def _validate_action_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
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
                    self._validate_operation_execution(
                        stmt,
                        lambda looking_at: self._validate_looked_at_in_action(
                            looking_at, scope
                        ),
                    )

    def _validate_value_setting(
        self,
        stmt: ast.ValueSettingStatement,
        scope: scope_tracker.ScopeTracker,
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
        name_diagnostics = name_validators.validate_typed_name(
            potential_literal, self._definition
        )
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return False
        self._process_reference(potential_literal)
        return True

    def _validate_local_position_definition(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_local_name_format_and_conflicts(local_def, scope)
        if local_def.constraints is not None:
            self._validate_position_requirements(
                local_def.constraints.requirements,
                multiple_values_diagnostic=diagnostics.PositionMultipleValueConstraintsDiagnostic,
            )

    def _validate_local_name_format_and_conflicts(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.ScopeTracker,
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
                    location=local_def.typed_name.name_content.location,
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
        scope: scope_tracker.ScopeTracker,
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
        scope: scope_tracker.ScopeTracker,
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
        scope: scope_tracker.ScopeTracker,
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
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Validate a full chained name reference.

        Returns whether the caller may continue processing this reference.
        """
        first = chain.typed_names[0]
        last_typed_name = chain.typed_names[-1]
        may_continue = True

        if (
            isinstance(first, ast.LocalTypedNameReference)
            and first in self._unreferenced_positions
        ):
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

        if not scope.is_defined(first) and isinstance(
            first, ast.LocalTypedNameReference
        ):
            self._diagnostics.append(
                diagnostics.UndefinedLocalNameDiagnostic(
                    location=first.location,
                    local_name=first.full_typed_name,
                )
            )
            may_continue = False

        if not is_self_reference and isinstance(first, ast.GlobalTypedNameReference):
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
                and isinstance(typed_name, ast.LocalTypedNameReference)
                and not (
                    isinstance(previous_element, ast.GlobalTypedNameReference)
                    and previous_element.name_type == ast.NameType.ACTION
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

        if last_typed_name.name_type != ast.NameType.POSITION:
            self._diagnostics.append(
                diagnostics.PositionReferenceChainEndDiagnostic(
                    location=last_typed_name.location,
                )
            )
            may_continue = False

        return may_continue

    def _validate_chained_name_element(
        self,
        chain_element: ast.TypedNameReference,
    ):
        """Validate a single chain element.

        Returns whether or not the name was valid.
        """
        name_diagnostics = name_validators.validate_typed_name(
            chain_element, self._definition
        )
        self._diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return

        if isinstance(chain_element, ast.GlobalTypedNameReference):
            self._process_reference(chain_element)
        elif chain_element.name_type == ast.NameType.ACTION:
            self._diagnostics.append(
                diagnostics.LocalActionNameDiagnostic(
                    location=chain_element.location,
                    local_name=chain_element.name_content.name,
                )
            )

    def _validate_position_requirements(
        self,
        requirements: Sequence[ast.PositionRequirementStatement],
        *,
        multiple_values_diagnostic: type[
            diagnostics.MultipleValueConstraintsDiagnostic
        ],
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        first_value: ast.GlobalTypedNameReference | None = None
        for requirement in requirements:
            reference_diagnostics = name_validators.validate_typed_name(
                requirement.typed_global_name, self._definition
            )
            self._diagnostics.extend(reference_diagnostics)
            if reference_diagnostics:
                continue
            first_line = seen_lines.get(requirement.typed_global_name)
            if first_line is not None:
                self._diagnostics.append(
                    diagnostics.DuplicatePositionConstraintDiagnostic(
                        location=requirement.typed_global_name.location,
                        constraint_name=requirement.typed_global_name.source_typed_name,
                        first_constraint_line=first_line,
                    )
                )
                continue
            seen_lines[requirement.typed_global_name] = (
                requirement.typed_global_name.location.line
            )
            if requirement.typed_global_name.name_type == ast.NameType.VALUE:
                if first_value is not None:
                    self._diagnostics.append(
                        multiple_values_diagnostic(
                            location=requirement.typed_global_name.location,
                            first_value_name=first_value.source_typed_name,
                            first_constraint_line=first_value.location.line,
                        )
                    )
                    continue
                first_value = requirement.typed_global_name
            self._process_reference(requirement.typed_global_name)

    def _validate_quality_implications(
        self,
        implications: tuple[ast.QualityImplicationStatement, ...],
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        for implication in implications:
            name_diagnostics = name_validators.validate_typed_name(
                implication.typed_global_name, self._definition
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
                    location=local_def.typed_name.name_content.location,
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

        is_self_reference = (
            typed_global_name.full_typed_name
            == self._definition.typed_name.source_typed_name
        )
        # Only the first reference site per target emits an edge; downstream
        # per-target diagnostics (missing file, cycle, wrong type) then fire
        # once per (definition, target) pair instead of once per source line.
        if typed_global_name.full_typed_name in self._seen_edge_targets:
            return
        self._seen_edge_targets.add(typed_global_name.full_typed_name)

        is_same_file_reference = (
            typed_global_name in self._seen_definitions or is_self_reference
        )
        # Process a cross-FQUN reference in a filesystem context. References
        # that resolve within this same file skip the sub-root check so that
        # they still get edges for same-file validation. The standard universe
        # is built into the compiler, so it has no sub-root.
        # TODO: Stop exempting the standard universe once the Define Standard
        # Library defines the built-in names.
        if (
            global_name.fqun is not None
            and global_name.fqun.canonical != constants.STANDARD_UNIVERSE
            and not is_same_file_reference
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
