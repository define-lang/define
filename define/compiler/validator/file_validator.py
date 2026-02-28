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
    name_validators,
    scope_tracker,
    stats,
    validation_result,
)

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
        try:
            tree = self._parser.parse(source, file_path=context.full_path)
        except SYNTAX_ERROR_TYPES as e:
            tracker.mark_parse_finished()
            return validation_result.ValidationResult(
                diagnostics=[],
                exception=e,
                source=source,
                file_path=context.full_path,
                root_prefix=context.root_prefix,
                stats=tracker.build(),
            )
        tracker.mark_parse_finished()

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
        return validation_result.ValidationResult(
            diagnostics=fdv.diagnostics,
            exception=None,
            source=source,
            file_path=context.full_path,
            root_prefix=context.root_prefix,
            stats=tracker.build(),
            definitions=fdv.definitions,
            reference_edges=fdv.reference_edges,
            discovered_files=fdv.discovered_files,
            deferred_chained_names=fdv.deferred_chained_names,
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
        scope.enter_child_scope()
        self._validate_action_statements(
            definition_block.action_statements,
            enclosing_definition,
            scope,
        )

    def _validate_action_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    self._validate_local_position_definition(
                        stmt, enclosing_definition, scope
                    )
                case ast.CreateDimensionPointStatement():
                    self._validate_create_dimension_point(
                        stmt, enclosing_definition, scope
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
            name_validators.validate_local_name_format(local_def.local_name)
        )
        name = local_def.local_name.name
        # TODO: LocalPositionDefinition needs to have a typed_name field.
        typed_ref = ast.LocalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=local_def.local_name,
            position=local_def.position,
        )
        first_def = scope.get_definition(typed_ref)
        if first_def is not None:
            self.diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    position=local_def.local_name.position,
                    local_name=name,
                    first_definition_line=first_def.local_name.position.line,
                )
            )
            return
        scope.add_local_definition(local_def)

    def _validate_create_dimension_point(
        self,
        stmt: ast.CreateDimensionPointStatement,
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        self._validate_full_chained_name(
            stmt.position_reference.chain, enclosing_definition, scope
        )

    def _validate_full_chained_name(
        self,
        chain: list[ast.TypedName],
        enclosing_definition: ast.QualityDefinition,
        scope: scope_tracker.ScopeTracker,
    ):
        first = chain[0]
        first_is_defined = True
        if not scope.is_defined(first):
            first_is_defined = False
            if isinstance(first, ast.LocalTypedNameReference):
                fqun = enclosing_definition.typed_name.name_content.fqun
                self.diagnostics.append(
                    diagnostics.UndefinedLocalNameDiagnostic(
                        position=first.name_content.position,
                        local_name=first.full_typed_name(in_universe=fqun),
                    )
                )
            # TODO: Support global names starting positions.

        for typed_name in chain:
            self._validate_chained_name_element(typed_name, enclosing_definition)

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
            # We don't need to check name validation, because this doesn't cause
            # file I/O. (Only emitting a DiscoveredFile triggers that.)
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
