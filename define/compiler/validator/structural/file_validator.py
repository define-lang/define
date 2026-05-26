"""Pure per-file validation for the Define language.

FileStructuralValidator is a stateless worker that processes one file at a time.
It takes immutable inputs and produces immutable outputs, with no access
to shared mutable state.
"""

from __future__ import annotations

import pathlib
import typing
from dataclasses import dataclass
from functools import cached_property

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

from define.compiler import (
    ast,
    constants,
    diagnostics,
    exceptions,
    parser,
    parser_error_classification,
    parser_exceptions,
    transformer,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.graphs import reference_graph
from define.compiler.lark import lark_standalone
from define.compiler.validator import scope_tracker, stats, validation_result
from define.compiler.validator.structural import name_validators

SYNTAX_ERROR_TYPES = (
    parser_exceptions.DefineSyntaxError,
    lark_standalone.UnexpectedInput,
)


@dataclass(frozen=True)
class FileValidationContext:
    """Immutable input for validating a single file."""

    file_path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    sub_root_mappings: Mapping[str, pathlib.PurePosixPath] | None = None
    is_filesystem_context: bool = True

    @cached_property
    def full_path(self) -> pathlib.PurePosixPath:
        """Return full filesystem path for this validation context."""
        return self.root_prefix / self.file_path

    @cached_property
    def expected_definition_path(self) -> pathlib.PurePosixPath | None:
        """Return the expected definition path for filesystem-backed validation."""
        return self.file_path.with_suffix("")


@dataclass(frozen=True)
class EmptyFileValidationContext(FileValidationContext):
    """Validation context for non-filesystem source validation."""

    file_path: pathlib.PurePosixPath = constants.NON_FILESYSTEM_PATH
    root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT
    expected_fqun: str = ""
    sub_root_mappings: Mapping[str, pathlib.PurePosixPath] | None = None
    is_filesystem_context: bool = False

    @cached_property
    def expected_definition_path(self) -> pathlib.PurePosixPath | None:
        """Return no expected definition path for source-only validation."""
        return None


class FileStructuralValidator:
    """Stateless per-file validator.

    Processes one file: reads from disk, parses, transforms, and validates
    local rules. Produces a FileValidationResult with discovered files and
    reference edges for the coordinator to process.
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
                source=None,
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
        parse_result = self._parser.parse(source, file_path=context.full_path)
        tracker.mark_parse_finished()

        if parse_result.exception is not None:
            indentation_diags: list[diagnostics.Diagnostic] = (
                parse_result.diagnostics if context.is_filesystem_context else []
            )
            return validation_result.FileValidationResult(
                exception=parse_result.exception,
                source=source,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
                file_diagnostics=indentation_diags,
                definition_results=[],
            )

        # tree is guaranteed non-None when exception is None.
        tree = typing.cast(
            "lark_standalone.Tree[lark_standalone.Token]", parse_result.tree
        )

        file_path = context.full_path if context.is_filesystem_context else None
        try:
            program = transformer.DefineTransformer(file_path=file_path).transform(tree)
        except (
            lark_standalone.VisitError,
            parser_exceptions.DefineSyntaxError,
        ) as e:
            if isinstance(e, lark_standalone.VisitError):
                if not isinstance(e.orig_exc, SYNTAX_ERROR_TYPES):
                    raise
                syntax_error = e.orig_exc
            else:
                syntax_error = e
            tracker.mark_transform_finished()
            return validation_result.FileValidationResult(
                exception=syntax_error,
                source=source,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
                file_diagnostics=[],
                definition_results=[],
            )
        tracker.mark_transform_finished()

        seen_definitions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedNameInDefinition, ast.QualityDefinition
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
            source=source,
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
        path: pathlib.PurePosixPath,
    ) -> tuple[str, validation_result.AnyValidationException | None]:
        """Load a Define source file and return source and syntax errors."""
        try:
            with open(pathlib.Path(path), "rb") as source_file:
                raw = source_file.read()
        except FileNotFoundError:
            return "", exceptions.SourceFileNotFoundError(
                filesystem_path=pathlib.Path(path)
            )
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            return "", parser_error_classification.make_invalid_encoding_error(
                raw, e, path
            )
        return source, None


class DefinitionStructuralValidator:
    """Validates one definition within a single file.

    Is mutable and not thread-safe.
    """

    _context: FileValidationContext
    _diagnostics: list[diagnostics.Diagnostic]
    _definition: ast.QualityDefinition
    _reference_edges: list[reference_graph.ReferenceEdge]
    _seen_edge_targets: set[str]
    _discovered_files: list[validation_result.DiscoveredFile]
    _discovered_file_keys: set[tuple[pathlib.PurePosixPath, str]]
    _dp_statement_validity: list[validation_result.DimensionPointStatementValidity]
    _seen_definitions: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameInDefinition, ast.QualityDefinition
    ]
    _unknown_fquns: set[str]
    _implied_qualities: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameReference, ast.QualityImplicationStatement
    ]
    _used_implied_qualities: set[str]

    def __init__(
        self,
        definition: ast.QualityDefinition,
        context: FileValidationContext,
        seen_definitions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedNameInDefinition, ast.QualityDefinition
        ],
    ):
        """Initialize per-definition validation state from file-level state."""
        self._definition = definition
        self._context = context
        self._diagnostics = []
        self._reference_edges = []
        self._seen_edge_targets = set()
        self._discovered_files = []
        self._discovered_file_keys = set()
        self._dp_statement_validity = []
        self._seen_definitions = seen_definitions
        self._unknown_fquns = set()
        self._implied_qualities = typed_name_dict.TypedNameDict()
        self._used_implied_qualities = set()

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

        if isinstance(self._definition, ast.ActionDefinition):
            self._validate_action_definition(self._definition)
        if isinstance(self._definition, ast.PositionDefinition):
            self._validate_global_position_definition_block(self._definition)
        return self.build_result()

    def build_result(self) -> validation_result.DefinitionValidationResult:
        """Build a result object from the validator's private state."""
        return validation_result.DefinitionValidationResult(
            definition=self._definition,
            _diagnostics=self._diagnostics,
            reference_edges=self._reference_edges,
            discovered_files=self._discovered_files,
            dp_statement_validity=self._dp_statement_validity,
        )

    def _validate_path_matches_file(self):
        if self._context.expected_definition_path is None:
            return
        definition_path = self._definition.typed_name.name_content.path.name
        expected_path = "/" + self._context.expected_definition_path.as_posix()
        if definition_path != expected_path:
            self._diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    location=self._definition.typed_name.name_content.path.location,
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_fqun_matches_expected(self):
        expected_fqun = self._context.expected_fqun
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
        self._check_unused_quality_implications()

    def _validate_global_position_definition_block(
        self,
        definition: ast.PositionDefinition,
    ):
        self._validate_quality_implications(definition.quality_implications)
        if definition.constraints:
            self._validate_position_constraints(definition.constraints)
        if definition.initialization is not None:
            scope = scope_tracker.ScopeTracker()
            scope.add_definition(definition)
            self._validate_action_statements(
                definition.initialization,
                scope,
                allow_self_reference=True,
            )
        self._check_unused_quality_implications()

    def _validate_trigger_conditions(
        self,
        trigger_conditions: ast.TriggerConditionsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        for condition in trigger_conditions.conditions:
            if isinstance(condition, ast.PositionPresenceStatement):
                _ = self._validate_full_chained_name(
                    condition.position_reference, scope
                )

    def _validate_action_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
        *,
        allow_self_reference: bool = False,
    ):
        if not action_statements.statements:
            if isinstance(action_statements, ast.PositionInitBlock):
                self._diagnostics.append(
                    diagnostics.EmptyPositionInitBlockDiagnostic(
                        location=action_statements.location,
                    )
                )
            else:
                self._diagnostics.append(
                    diagnostics.EmptyActionStatementsBlockDiagnostic(
                        location=action_statements.location,
                    )
                )
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    self._validate_local_position_definition(stmt, scope)
                case ast.CreateDimensionPointStatement():
                    self._validate_create_dimension_point(
                        stmt, scope, allow_self_reference=allow_self_reference
                    )
                case ast.MoveDimensionPointStatement():
                    self._validate_move_dimension_point(
                        stmt, scope, allow_self_reference=allow_self_reference
                    )
                case ast.DestroyDimensionPointStatement():
                    self._validate_destroy_dimension_point(
                        stmt, scope, allow_self_reference=allow_self_reference
                    )

    def _validate_local_position_definition(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_local_name_format_and_conflicts(local_def, scope)
        if local_def.constraints is not None:
            self._validate_position_constraints(local_def.constraints)

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

    def _validate_create_dimension_point(
        self,
        stmt: ast.CreateDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
        *,
        allow_self_reference: bool = False,
    ):
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
            allow_self_reference=allow_self_reference,
        )
        self._dp_statement_validity.append(
            validation_result.DimensionPointStatementValidity(
                target_ok=target_ok,
            )
        )

    def _validate_move_dimension_point(
        self,
        stmt: ast.MoveDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
        *,
        allow_self_reference: bool = False,
    ):
        source_ok = self._validate_full_chained_name(
            stmt.source_position,
            scope,
            allow_self_reference=allow_self_reference,
        )
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
            allow_self_reference=allow_self_reference,
        )
        from_is_prefix_of_to = self._check_if_from_is_a_prefix_of_to(stmt)
        self._dp_statement_validity.append(
            validation_result.DimensionPointStatementValidity(
                source_ok=source_ok,
                target_ok=target_ok,
                from_is_prefix_of_to=from_is_prefix_of_to,
            )
        )

    def _check_if_from_is_a_prefix_of_to(
        self,
        stmt: ast.MoveDimensionPointStatement,
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

    def _validate_destroy_dimension_point(
        self,
        stmt: ast.DestroyDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
        *,
        allow_self_reference: bool = False,
    ):
        target_ok = self._validate_full_chained_name(
            stmt.target_position,
            scope,
            allow_self_reference=allow_self_reference,
        )
        self._dp_statement_validity.append(
            validation_result.DimensionPointStatementValidity(
                target_ok=target_ok,
            )
        )

    def _validate_full_chained_name(
        self,
        chain: ast.ChainedName,
        scope: scope_tracker.ScopeTracker,
        *,
        allow_self_reference: bool = False,
    ) -> bool:
        """Validate a full chained name reference.

        Returns whether the caller may continue processing this reference.
        """
        first = chain.typed_names[0]
        may_continue = True

        is_self_reference = (
            first.full_typed_name == self._definition.typed_name.source_typed_name
        )
        is_chained_self_reference = is_self_reference and len(chain.typed_names) > 1
        if is_chained_self_reference and not allow_self_reference:
            self._diagnostics.append(
                diagnostics.UnnecessarySelfReferenceDiagnostic(
                    location=first.location,
                    definition_name=self._definition.typed_name.source_typed_name,
                )
            )
            # NOTE: Mutates the AST so downstream validation sees the corrected chain.
            # Otherwise things like duplicate detection would not correctly trigger.
            del chain.typed_names[0]
            first = chain.typed_names[0]

        if not scope.is_defined(first) and isinstance(
            first, ast.LocalTypedNameReference
        ):
            # TODO: Use first.location instead of name_content.location.
            self._diagnostics.append(
                diagnostics.UndefinedLocalNameDiagnostic(
                    location=first.name_content.location,
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
            self._validate_chained_name_element(
                typed_name, allow_self_reference=allow_self_reference
            )
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

        if chain.typed_names[-1].name_type != ast.NameType.POSITION:
            self._diagnostics.append(
                diagnostics.PositionReferenceChainEndDiagnostic(
                    location=chain.typed_names[-1].location,
                )
            )
            may_continue = False

        return may_continue

    def _validate_chained_name_element(
        self,
        chain_element: ast.TypedNameReference,
        *,
        allow_self_reference: bool = False,
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
            self._process_reference(
                chain_element, allow_self_reference=allow_self_reference
            )
        elif chain_element.name_type == ast.NameType.ACTION:
            # TODO: Use chain_element.location instead of name_content.location.
            self._diagnostics.append(
                diagnostics.LocalActionNameDiagnostic(
                    location=chain_element.name_content.location,
                    local_name=chain_element.name_content.name,
                )
            )

    def _validate_position_constraints(
        self,
        constraints: ast.PositionConstraintBlock,
    ):
        seen_lines: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        for requirement in constraints.requirements:
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
            self._process_reference(requirement.typed_global_name)

    def _validate_quality_implications(
        self,
        implications: list[ast.QualityImplicationStatement],
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
        *,
        allow_self_reference: bool = False,
    ):
        """Record a reference edge and determine the target file to discover."""
        global_name = typed_global_name.name_content

        # In Position Initialization Blocks, self-references don't cause us
        # to do file loads. They are not actually external references.
        is_self_reference = (
            typed_global_name.full_typed_name
            == self._definition.typed_name.source_typed_name
        )
        if is_self_reference and allow_self_reference:
            return
        # Only the first reference site per target emits an edge; downstream
        # per-target diagnostics (missing file, cycle, wrong type) then fire
        # once per (definition, target) pair instead of once per source line.
        if typed_global_name.full_typed_name in self._seen_edge_targets:
            return
        self._seen_edge_targets.add(typed_global_name.full_typed_name)
        # Process a reference that's inside of this same file.
        if typed_global_name in self._seen_definitions or is_self_reference:
            self._reference_edges.append(
                reference_graph.ReferenceEdge(
                    enclosing_definition=self._definition,
                    global_name_reference=typed_global_name,
                )
            )
            return

        if global_name.fqun is None:
            # Process a reference from this universe.
            self._add_edge_and_discovered_file(
                typed_global_name=typed_global_name,
                global_name=global_name,
                root_prefix=self._context.root_prefix,
                expected_fqun=self._definition.typed_name.name_content.fqun,
            )
            return

        sub_root_mappings = self._context.sub_root_mappings
        if not self._context.is_filesystem_context:
            # Process a cross-FQUN reference in a non-filesystem context.
            self._add_edge_and_discovered_file(
                typed_global_name=typed_global_name,
                global_name=global_name,
                root_prefix=self._context.root_prefix,
                expected_fqun=global_name.fqun,
            )
            return
        if sub_root_mappings is None:
            raise ValueError("filesystem contexts must define sub_root_mappings")

        # Process a cross-FQUN reference in a filesystem context.
        fqun_string = global_name.fqun.canonical
        if fqun_string in self._unknown_fquns:
            return
        if fqun_string not in sub_root_mappings:
            self._unknown_fquns.add(fqun_string)
            self._diagnostics.append(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    location=global_name.fqun.location,
                    universe=fqun_string,
                    current_universe_name=self._context.expected_fqun,
                )
            )
            return
        sub_root_rel = sub_root_mappings[fqun_string]
        self._add_edge_and_discovered_file(
            typed_global_name=typed_global_name,
            global_name=global_name,
            root_prefix=self._context.root_prefix / sub_root_rel,
            expected_fqun=global_name.fqun,
        )

    def _add_edge_and_discovered_file(
        self,
        typed_global_name: ast.GlobalTypedNameReference,
        global_name: ast.ReferenceGlobalNameContent,
        root_prefix: pathlib.PurePosixPath,
        expected_fqun: ast.Fqun,
    ):
        self._reference_edges.append(
            reference_graph.ReferenceEdge(
                enclosing_definition=self._definition,
                global_name_reference=typed_global_name,
            )
        )
        key = (root_prefix, global_name.path.name)
        if key in self._discovered_file_keys:
            return
        self._discovered_file_keys.add(key)
        self._discovered_files.append(
            validation_result.DiscoveredFile(
                path=global_name.path.file_path(),
                root_prefix=root_prefix,
                expected_fqun=expected_fqun.canonical,
                location=global_name.location,
            )
        )
