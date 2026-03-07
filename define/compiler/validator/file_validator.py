"""Pure per-file validation for the Define language.

FileValidator is a stateless worker that processes one file at a time.
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
from define.compiler.lark import lark_standalone
from define.compiler.validator import (
    dimension_point_tracker,
    name_validators,
    scope_tracker,
    stats,
    validation_result,
)

SYNTAX_ERROR_TYPES = (
    parser_exceptions.DefineSyntaxError,
    lark_standalone.UnexpectedInput,
)


def _chain_name(chain: list[ast.TypedName]) -> str:
    """Format a chain of typed names as written in the source."""
    return "::".join(elem.source_typed_name for elem in chain)


@dataclass(frozen=True)
class FileValidationContext:
    """Immutable input for validating a single file."""

    file_path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    # If sub_root_mappings is None, we are in a non-filesystem context.
    sub_root_mappings: Mapping[str, pathlib.PurePosixPath] | None = None

    @cached_property
    def full_path(self) -> pathlib.PurePosixPath:
        """Return full filesystem path for this validation context."""
        return self.root_prefix / self.file_path


@dataclass(frozen=True)
class EmptyFileValidationContext(FileValidationContext):
    """Validation context for non-filesystem source validation."""

    file_path: pathlib.PurePosixPath = constants.NON_FILESYSTEM_PATH
    root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT
    expected_fqun: str = ""
    sub_root_mappings: Mapping[str, pathlib.PurePosixPath] | None = None


class FileValidator:
    """Stateless per-file validator.

    Processes one file: reads from disk, parses, transforms, and validates
    local rules. Produces a ValidationResult with discovered files and
    reference edges for the coordinator to process.
    """

    _parser: parser.Parser

    def __init__(self, lark_parser: parser.Parser):
        """Initialize with a shared parser instance."""
        self._parser = lark_parser

    def validate_file(
        self, context: FileValidationContext
    ) -> validation_result.ValidationResult:
        """Validate a single file and return the result."""
        tracker = stats.ValidationStatsTracker()

        source, load_error = self._load_file(context.full_path)
        tracker.mark_file_loading_finished()
        if load_error is not None:
            return validation_result.ValidationResult(
                diagnostics=[],
                exception=load_error,
                source=None,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
            )
        expected_definition_path = context.file_path.with_suffix("")
        return self._validate_source(
            context=context,
            source=source,
            tracker=tracker,
            expected_definition_path=expected_definition_path,
        )

    def validate_source(
        self,
        source: str,
    ) -> validation_result.ValidationResult:
        """Validate source text without loading from the filesystem."""
        context = EmptyFileValidationContext()
        tracker = stats.ValidationStatsTracker()
        tracker.mark_file_loading_finished()
        return self._validate_source(
            context=context,
            source=source,
            tracker=tracker,
            expected_definition_path=None,
        )

    def _validate_source(
        self,
        context: FileValidationContext,
        source: str,
        tracker: stats.ValidationStatsTracker,
        expected_definition_path: pathlib.PurePosixPath | None,
    ) -> validation_result.ValidationResult:
        """Parse, transform, and validate source text."""
        parse_result = self._parser.parse(source, file_path=context.full_path)
        tracker.mark_parse_finished()

        if parse_result.exception is not None:
            indentation_diags: list[diagnostics.Diagnostic] = (
                parse_result.diagnostics if expected_definition_path is not None else []
            )
            return validation_result.ValidationResult(
                diagnostics=indentation_diags,
                exception=parse_result.exception,
                source=source,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
            )

        # tree is guaranteed non-None when exception is None.
        tree = typing.cast(
            "lark_standalone.Tree[lark_standalone.Token]", parse_result.tree
        )

        try:
            program = transformer.DefineTransformer().transform(tree)
        except lark_standalone.VisitError as e:
            if isinstance(e.orig_exc, SYNTAX_ERROR_TYPES):
                tracker.mark_transform_finished()
                return validation_result.ValidationResult(
                    diagnostics=[],
                    exception=e.orig_exc,
                    source=source,
                    file_path=context.full_path,
                    root_prefix=context.root_prefix,
                    stats=tracker.build(),
                )
            raise
        tracker.mark_transform_finished()

        fdv = ProgramAstValidator(context, expected_definition_path)
        fdv.validate_program(program)
        tracker.mark_file_validation_finished()

        all_diagnostics = fdv.diagnostics
        if expected_definition_path is not None:
            all_diagnostics = parse_result.diagnostics + all_diagnostics

        # TODO: It seems like we should actually be returning results per definition processed.
        return validation_result.ValidationResult(
            diagnostics=all_diagnostics,
            exception=None,
            source=source,
            file_path=context.full_path,
            root_prefix=context.root_prefix,
            stats=tracker.build(),
            definitions=fdv.definitions,
            reference_edges=fdv.reference_edges,
            discovered_files=fdv.discovered_files,
            deferred_chained_names=fdv.deferred_chained_names,
            trigger_positions=fdv.trigger_positions,
            action_body_effects=fdv.action_body_effects,
            deferred_move_constraint_checks=fdv.deferred_move_constraint_checks,
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


class ProgramAstValidator:
    """Validates definitions within a single file.

    Tracks within-file state: local duplicates, diagnostics, and discovered
    references. Does NOT access any cross-file shared state.

    Is mutable and not thread-safe.
    """

    _context: FileValidationContext
    _expected_definition_path: pathlib.PurePosixPath | None
    diagnostics: list[diagnostics.Diagnostic]
    definitions: list[ast.QualityDefinition]
    reference_edges: list[validation_result.ReferenceEdge]
    discovered_files: list[validation_result.DiscoveredFile]
    deferred_chained_names: list[validation_result.DeferredChainElements]
    trigger_positions: list[validation_result.TriggerPositionInfo]
    action_body_effects: list[validation_result.ActionBodyEffect]
    deferred_move_constraint_checks: list[validation_result.DeferredMoveConstraintCheck]
    _seen_in_file: dict[str, ast.QualityDefinition]
    _unknown_fquns: set[str]

    def __init__(
        self,
        context: FileValidationContext,
        expected_definition_path: pathlib.PurePosixPath | None,
    ):
        """Initialize per-file validation state."""
        self._context = context
        self._expected_definition_path = expected_definition_path
        self.diagnostics = []
        self.definitions = []
        self.reference_edges = []
        self.discovered_files = []
        self.deferred_chained_names = []
        self.trigger_positions = []
        self.action_body_effects = []
        self.deferred_move_constraint_checks = []
        self._seen_in_file = {}
        self._unknown_fquns = set()

    def validate_program(self, program: ast.Program):
        """Validate all definitions in the program."""
        for definition in program.definitions:
            self._validate_definition(definition)

    def _validate_definition(self, definition: ast.QualityDefinition):
        self.diagnostics.extend(
            name_validators.validate_global_name(definition.typed_name.name_content)
        )
        self._validate_path_matches_file(definition)
        self._validate_fqun_matches_expected(definition)
        is_duplicate = self._validate_not_duplicate_in_file(definition)
        if not is_duplicate:
            self.definitions.append(definition)

        if (
            isinstance(definition, ast.ActionDefinition)
            and definition.definition_block is not None
        ):
            self._validate_action_definition_block(
                definition.definition_block,
                definition,
            )
        if isinstance(definition, ast.PositionDefinition) and definition.constraints:
            self._validate_position_constraints(
                definition.constraints,
                definition,
            )

    def _validate_path_matches_file(self, definition: ast.QualityDefinition):
        if self._expected_definition_path is None:
            return
        definition_path = definition.typed_name.name_content.path.name
        expected_path = "/" + self._expected_definition_path.as_posix()
        if definition_path != expected_path:
            self.diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    position=definition.typed_name.name_content.path.position,
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_fqun_matches_expected(self, definition: ast.QualityDefinition):
        expected_fqun = self._context.expected_fqun
        if not expected_fqun:
            return
        actual = definition.typed_name.name_content.fqun.canonical
        if actual != expected_fqun:
            self.diagnostics.append(
                diagnostics.FqunMismatchDiagnostic(
                    position=definition.typed_name.name_content.fqun.position,
                    expected=expected_fqun,
                    actual=actual,
                )
            )

    def _validate_not_duplicate_in_file(
        self, definition: ast.QualityDefinition
    ) -> bool:
        """Check for within-file duplicates. Returns True if duplicate."""
        key = definition.typed_name.full_typed_name()
        if key in self._seen_in_file:
            first_def = self._seen_in_file[key]
            self.diagnostics.append(
                diagnostics.DuplicateDefinitionDiagnostic(
                    position=definition.position,
                    definition_type=definition.typed_name.name_type.value,
                    path=definition.typed_name.name_content.path.name,
                    first_definition_line=first_def.position.line,
                )
            )
            return True
        self._seen_in_file[key] = definition
        return False

    def _validate_action_definition_block(
        self,
        definition_block: ast.ActionDefinitionBlock,
        enclosing_definition: ast.QualityDefinition,
    ):
        scope = scope_tracker.ScopeTracker(
            enclosing_definition.typed_name.name_content.fqun
        )
        for local_def in definition_block.local_definitions:
            self._validate_local_position_definition(
                local_def, enclosing_definition, scope
            )
        self._validate_trigger_conditions(
            definition_block.trigger_conditions, enclosing_definition, scope
        )
        tracker = dimension_point_tracker.LocalDimensionPointTracker(
            enclosing_definition
        )
        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        for condition in definition_block.trigger_conditions.conditions:
            ref = condition.position_reference
            local_ref = tracker.get_local_position_reference(ref, scope)
            if local_ref is not None:
                qualities = scope.get_constraint_names(ref.chain[0])
                tracker.create(ref, qualities)
        scope.enter_child_scope()
        self._validate_action_statements(
            definition_block.action_statements,
            enclosing_definition,
            scope,
            tracker,
        )

    def _validate_trigger_conditions(
        self,
        trigger_conditions: ast.TriggerConditionsBlock,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        for condition in trigger_conditions.conditions:
            chain = condition.position_reference.chain
            if not self._validate_full_chained_name(chain, enclosing_definition, scope):
                continue
            self.trigger_positions.append(
                validation_result.TriggerPositionInfo(
                    enclosing_typed_name=enclosing_definition.typed_name,
                    checked_position=chain,
                )
            )

    def _validate_action_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    self._validate_local_position_definition(
                        stmt, enclosing_definition, scope
                    )
                case ast.CreateDimensionPointStatement():
                    self._validate_create_dimension_point(
                        stmt, enclosing_definition, scope, tracker
                    )
                case ast.MoveDimensionPointStatement():
                    self._validate_move_dimension_point(
                        stmt, enclosing_definition, scope, tracker
                    )

    def _validate_local_position_definition(
        self,
        local_def: ast.LocalPositionDefinition,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_local_name_format_and_conflicts(local_def, scope)
        if local_def.constraints is not None:
            self._validate_position_constraints(
                local_def.constraints,
                enclosing_definition,
            )

    def _validate_local_name_format_and_conflicts(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        self.diagnostics.extend(
            name_validators.validate_local_name_format(
                local_def.typed_name.name_content
            )
        )
        name = local_def.typed_name.name_content.name
        first_def = scope.get_definition(local_def.typed_name)
        if first_def is not None:
            self.diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    position=local_def.typed_name.name_content.position,
                    local_name=name,
                    first_definition_line=first_def.typed_name.name_content.position.line,
                )
            )
            return
        scope.add_local_definition(local_def)

    def _validate_create_dimension_point(
        self,
        stmt: ast.CreateDimensionPointStatement,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        position = stmt.position_reference
        if not self._validate_full_chained_name(
            position.chain, enclosing_definition, scope
        ):
            return

        if tracker.has_unknown_state(position):
            return

        local_ref = tracker.get_local_position_reference(position, scope)
        if local_ref is not None:
            if tracker.is_occupied(position):
                existing = tracker.get_occupant(position)
                self.diagnostics.append(
                    diagnostics.LocalDuplicateDimensionPointDiagnostic(
                        position=position.position,
                        position_name=_chain_name(position.chain),
                        first_creation_line=existing.creation_position.position.line,
                    )
                )
                return
            qualities = scope.get_constraint_names(position.chain[0])
            tracker.create(position, qualities)

        self.action_body_effects.append(
            validation_result.ActionBodyEffect(
                enclosing_typed_name=enclosing_definition.typed_name,
                statement=stmt,
            )
        )

    def _validate_move_dimension_point(
        self,
        stmt: ast.MoveDimensionPointStatement,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        from_ok = self._validate_full_chained_name(
            stmt.from_position.chain, enclosing_definition, scope
        )
        to_ok = self._validate_full_chained_name(
            stmt.to_position.chain, enclosing_definition, scope
        )
        fqun = enclosing_definition.typed_name.name_content.fqun
        if self._check_if_from_is_a_prefix_of_to(stmt, fqun, scope, tracker):
            return
        if not (from_ok and to_ok):
            return

        self._execute_move(stmt, enclosing_definition, scope, tracker)

    def _execute_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ):
        # First, if either position is in an unknown state, mark both as now having an
        # unknown state and don't do any more checks.
        if tracker.has_unknown_state(stmt.from_position) or tracker.has_unknown_state(
            stmt.to_position
        ):
            tracker.mark_unknown_state(stmt.from_position)
            tracker.mark_unknown_state(stmt.to_position)
            return

        from_local = tracker.get_local_position_reference(stmt.from_position, scope)
        to_local = tracker.get_local_position_reference(stmt.to_position, scope)

        from_occupied = tracker.is_occupied(stmt.from_position)
        to_empty = not tracker.is_occupied(stmt.to_position)

        if not (from_local and to_local):
            # For now, we are assuming that all external positions are fine to
            # move into or from, for the sake of simplicity.
            #
            # TODO: Need to do occupancy tracking on external positions, or more
            # realistically, need to have constraints that enforce that state.
            from_occupied = (not from_local) or from_occupied
            to_empty = (not to_local) or to_empty

        if not from_occupied:
            self.diagnostics.append(
                diagnostics.MoveFromEmptyPositionDiagnostic(
                    position=stmt.from_position.position,
                    position_name=_chain_name(stmt.from_position.chain),
                )
            )
        if not to_empty:
            occupant = tracker.get_occupant(stmt.to_position)
            occupied_at_line = (
                occupant.creation_position.position.line if occupant else None
            )
            self.diagnostics.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    position=stmt.to_position.position,
                    position_name=_chain_name(stmt.to_position.chain),
                    occupied_at_line=occupied_at_line,
                )
            )

        if not (from_occupied and to_empty):
            tracker.mark_unknown_state(stmt.from_position)
            tracker.mark_unknown_state(stmt.to_position)
            return

        if from_local and to_local:
            if self._check_constraints_for_move(stmt, scope, tracker):
                tracker.move(stmt.from_position, stmt.to_position)
        else:
            # Chained→chained: both sides need resolution by program validator.
            from_qualities = None
            to_qualities = None
            if from_local:
                # Local→chained: we know the from qualities locally.
                from_qualities = tracker.get_occupant(stmt.from_position).qualities
                tracker.destroy(stmt.from_position)
            elif to_local:
                # Chained→local: we know the to qualities locally.
                to_qualities = scope.get_constraint_names(stmt.to_position.chain[0])
                tracker.create(stmt.to_position, to_qualities)
            self.deferred_move_constraint_checks.append(
                validation_result.DeferredMoveConstraintCheck(
                    enclosing_definition=enclosing_definition,
                    statement=stmt,
                    from_qualities=from_qualities,
                    to_qualities=to_qualities,
                )
            )

        if not tracker.has_unknown_state(stmt.to_position):
            self.action_body_effects.append(
                validation_result.ActionBodyEffect(
                    enclosing_typed_name=enclosing_definition.typed_name,
                    statement=stmt,
                )
            )

    def _check_constraints_for_move(
        self,
        stmt: ast.MoveDimensionPointStatement,
        scope: scope_tracker.ScopeTracker,
        tracker: dimension_point_tracker.LocalDimensionPointTracker,
    ) -> bool:
        """Check that a move satisfies destination constraints."""
        # TODO: Check constraints for non-local (chained/global) positions.
        dp_info = tracker.get_occupant(stmt.from_position)
        dest_constraints = scope.get_constraint_names(stmt.to_position.chain[0])
        missing_qualities = dest_constraints - dp_info.qualities
        if not missing_qualities:
            return True

        self.diagnostics.append(
            diagnostics.MoveViolatesConstraintsDiagnostic(
                position=stmt.to_position.chain[0].position,
                from_position=_chain_name(stmt.from_position.chain),
                to_position=_chain_name(stmt.to_position.chain),
                missing_qualities=sorted(missing_qualities),
            )
        )
        tracker.mark_unknown_state(stmt.from_position)
        tracker.mark_unknown_state(stmt.to_position)
        return False

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
        from_chain = stmt.from_position.chain
        to_chain = stmt.to_position.chain
        if len(from_chain) > len(to_chain):
            return False
        for from_elem, to_elem in zip(from_chain, to_chain, strict=False):
            if from_elem.full_typed_name(in_universe=fqun) != to_elem.full_typed_name(
                in_universe=fqun
            ):
                return False

        if len(from_chain) == len(to_chain):
            self.diagnostics.append(
                diagnostics.MoveToSamePositionDiagnostic(
                    position=to_chain[-1].position,
                    position_name=_chain_name(to_chain),
                )
            )
        else:
            divergence = to_chain[len(from_chain)]
            self.diagnostics.append(
                diagnostics.MoveIntoDefiningPositionDiagnostic(
                    position=divergence.position,
                    from_position=_chain_name(from_chain),
                    to_position=_chain_name(to_chain),
                )
            )
            # TODO: Need to export unknown-state positions in ValidationResult
            # so we know they also can't be checked elsewhere.
            if tracker.get_local_position_reference(stmt.from_position, scope):
                tracker.mark_unknown_state(stmt.from_position)
            if tracker.get_local_position_reference(stmt.to_position, scope):
                tracker.mark_unknown_state(stmt.to_position)
        return True

    def _validate_full_chained_name(
        self,
        chain: list[ast.TypedName],
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ) -> bool:
        """Validate a full chained name reference.

        Returns whether the caller may continue processing this reference.
        """
        first = chain[0]
        fqun = enclosing_definition.typed_name.name_content.fqun
        may_continue = True

        if (
            len(chain) > 1
            and isinstance(first, ast.GlobalTypedNameReference)
            and first.full_typed_name(in_universe=fqun)
            == enclosing_definition.typed_name.full_typed_name()
        ):
            self.diagnostics.append(
                diagnostics.UnnecessarySelfReferenceDiagnostic(
                    position=first.position,
                    definition_name=enclosing_definition.typed_name.full_typed_name(),
                )
            )
            # NOTE: Mutates the AST so downstream validation sees the corrected chain.
            # Otherwise things like duplicate detection would not correctly trigger.
            del chain[0]
            first = chain[0]

        first_is_defined = True
        if not scope.is_defined(first):
            first_is_defined = False
            if isinstance(first, ast.LocalTypedNameReference):
                self.diagnostics.append(
                    diagnostics.UndefinedLocalNameDiagnostic(
                        position=first.name_content.position,
                        local_name=first.full_typed_name(in_universe=fqun),
                    )
                )
                may_continue = False
            # TODO: Support global names starting positions.

        previous_element = None
        for typed_name in chain:
            self._validate_chained_name_element(typed_name, enclosing_definition)
            # Local names in chains may only come right after global action names.
            if (
                previous_element
                and isinstance(typed_name, ast.LocalTypedNameReference)
                and not (
                    isinstance(previous_element, ast.GlobalTypedNameReference)
                    and previous_element.name_type == ast.NameType.ACTION
                )
            ):
                self.diagnostics.append(
                    diagnostics.ChainedLocalNameRequiresActionDiagnostic(
                        position=typed_name.position,
                        local_name=typed_name.full_typed_name(in_universe=fqun),
                        preceding_name=previous_element.full_typed_name(
                            in_universe=fqun
                        ),
                    )
                )
                # Don't even try to process this name; it will fail when we try to
                # resolve it in program_validator.
                may_continue = False
            previous_element = typed_name

        if len(chain) > 1 and first_is_defined:
            # If the first item is a local position, we have to do the validation
            # of the second item immediately, because the constraint of the local
            # position won't be passed out of the function if it's in an Action
            # Statements Block. (If it's in an Action Definition Block, we still
            # _can_ do it now, so we simply should.)
            self._validate_chain_element_against_constraints(
                chain[1], chain[0], enclosing_definition, scope
            )

        # TODO: In the future when the _first_ element can be a global name, this will
        # be more complex.
        if len(chain) > 2 and isinstance(chain[1], ast.GlobalTypedNameReference):
            self.deferred_chained_names.append(
                validation_result.DeferredChainElements(
                    enclosing_definition=enclosing_definition,
                    parent_element=chain[1],
                    chain_element=chain[2],
                    remaining_chain=chain[3:],
                )
            )

        if chain[-1].name_type != ast.NameType.POSITION:
            self.diagnostics.append(
                diagnostics.PositionReferenceChainEndDiagnostic(
                    position=chain[-1].position,
                )
            )

        return may_continue

    def _validate_chained_name_element(
        self,
        chain_element: ast.TypedName,
        enclosing_definition: ast.QualityDefinition,
    ):
        """Validate a single chain element.

        Returns whether or not the name was valid.
        """
        name_diagnostics = name_validators.validate_typed_name(
            chain_element, enclosing_definition
        )
        self.diagnostics.extend(name_diagnostics)
        if name_diagnostics:
            return

        if isinstance(chain_element, ast.GlobalTypedNameReference):
            self._process_reference(chain_element, enclosing_definition)
        elif (
            isinstance(chain_element, ast.LocalTypedNameReference)
            and chain_element.name_type == ast.NameType.ACTION
        ):
            self.diagnostics.append(
                diagnostics.LocalActionNameDiagnostic(
                    position=chain_element.name_content.position,
                    local_name=chain_element.name_content.name,
                )
            )

    def _validate_chain_element_against_constraints(
        self,
        chain_element: ast.TypedName,
        parent: ast.TypedName,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check chain_element against parent's constraints. Returns True if valid."""
        if not scope.definition_has_quality(parent, chain_element):
            fqun = enclosing_definition.typed_name.name_content.fqun
            self.diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    position=chain_element.position,
                    element_name=chain_element.full_typed_name(in_universe=fqun),
                    parent_name=parent.full_typed_name(in_universe=fqun),
                )
            )

    def _validate_position_constraints(
        self,
        constraints: ast.PositionConstraintBlock,
        enclosing_definition: ast.QualityDefinition,
    ):
        for requirement in constraints.requirements:
            reference_diagnostics = name_validators.validate_typed_name(
                requirement.typed_global_name, enclosing_definition
            )
            self.diagnostics.extend(reference_diagnostics)
            if reference_diagnostics:
                continue
            self._process_reference(
                requirement.typed_global_name,
                enclosing_definition,
            )

    def _process_reference(
        self,
        typed_global_name: ast.GlobalTypedNameReference,
        enclosing_definition: ast.QualityDefinition,
    ):
        """Record a reference edge and determine the target file to discover."""
        global_name = typed_global_name.name_content
        edge = validation_result.ReferenceEdge(
            enclosing_definition=enclosing_definition,
            global_name_reference=typed_global_name,
        )
        # Process a reference that's inside of this same file.
        if edge.full_typed_name in self._seen_in_file:
            self.reference_edges.append(edge)
            return

        if global_name.fqun is None:
            # Process a reference from this universe.
            self._add_edge_and_discovered_file(
                edge=edge,
                global_name=global_name,
                root_prefix=self._context.root_prefix,
                expected_fqun=enclosing_definition.typed_name.name_content.fqun,
            )
            return

        sub_root_mappings = self._context.sub_root_mappings
        if sub_root_mappings is None:
            # Process a cross-FQUN reference in a non-filesystem context.
            self._add_edge_and_discovered_file(
                edge=edge,
                global_name=global_name,
                root_prefix=self._context.root_prefix,
                expected_fqun=global_name.fqun,
            )
            return

        # Process a cross-FQUN reference in a filesystem context.
        fqun_string = global_name.fqun.canonical
        if fqun_string in self._unknown_fquns:
            return
        if fqun_string not in sub_root_mappings:
            self._unknown_fquns.add(fqun_string)
            self.diagnostics.append(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    position=global_name.fqun.position,
                    universe=fqun_string,
                    current_universe_name=self._context.expected_fqun,
                )
            )
            return
        sub_root_rel = sub_root_mappings[fqun_string]
        self._add_edge_and_discovered_file(
            edge=edge,
            global_name=global_name,
            root_prefix=self._context.root_prefix / sub_root_rel,
            expected_fqun=global_name.fqun,
        )

    def _add_edge_and_discovered_file(
        self,
        edge: validation_result.ReferenceEdge,
        global_name: ast.ReferenceGlobalNameContent,
        root_prefix: pathlib.PurePosixPath,
        expected_fqun: ast.Fqun,
    ):
        self.reference_edges.append(edge)
        self.discovered_files.append(
            validation_result.DiscoveredFile(
                path=global_name.path.file_path(),
                root_prefix=root_prefix,
                expected_fqun=expected_fqun.canonical,
                position=global_name.position,
            )
        )
