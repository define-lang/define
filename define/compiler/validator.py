"""Semantic validation for the Define language AST."""

from __future__ import annotations

import pathlib
from collections import ChainMap
from dataclasses import dataclass
from functools import cached_property

from lark import exceptions as lark_exceptions

from define.compiler import (
    ast,
    config,
    constants,
    diagnostics,
    exceptions,
    name_validators,
    parser,
    parser_error_classification,
    parser_exceptions,
    path_tracker,
    stats,
    transformer,
)

ValidationTimingStats = stats.ValidationTimingStats

type AnyValidationException = exceptions.DefineError | lark_exceptions.UnexpectedInput
SYNTAX_ERROR_TYPES = (
    parser_exceptions.DefineSyntaxError,
    lark_exceptions.UnexpectedInput,
)


@dataclass
class ValidationResult:
    """Validation output for one source file."""

    diagnostics: list[diagnostics.Diagnostic]
    exception: AnyValidationException | None
    source: str | None
    file_path: pathlib.PurePosixPath
    stats: ValidationTimingStats


@dataclass
class _ValidationRun:
    """Tracks a single parse/validate run and builds consistent results."""

    file_path: pathlib.PurePosixPath
    stats: stats.ValidationStatsTracker
    source: str | None = None

    def incomplete(
        self,
        syntax_error: AnyValidationException,
    ) -> ValidationResult:
        return ValidationResult(
            diagnostics=[],
            exception=syntax_error,
            source=self.source,
            file_path=self.file_path,
            stats=self.stats.build(),
        )

    def complete(
        self, diagnostics_list: list[diagnostics.Diagnostic]
    ) -> ValidationResult:
        if self.source is None:
            raise ValueError("Source text was not recorded before success.")
        self.stats.mark_validate_finished()
        return ValidationResult(
            diagnostics=diagnostics_list,
            exception=None,
            source=self.source,
            file_path=self.file_path,
            stats=self.stats.build(),
        )


@dataclass
class _ValidationFrame:
    """Per-file validation context used by the validator call stack."""

    diagnostics: list[diagnostics.Diagnostic]
    expected_definition_path: pathlib.PurePosixPath | None
    root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT


# TODO: Factor this out into its own file.
class _ReferenceStack:
    """Tracks the global definitions we are currently walking, for cycle detection."""

    def __init__(self) -> None:
        self._stack: list[str] = []
        self._stack_index: dict[str, int] = {}

    def push(self, definition: ast.QualityDefinition) -> None:
        """Push one definition key onto the active stack."""
        definition_key = definition.fully_qualified_typed_name
        if definition_key in self._stack_index:
            raise ValueError(
                f"reference stack already contains definition: {definition_key}"
            )
        self._stack_index[definition_key] = len(self._stack)
        self._stack.append(definition_key)

    def pop(self) -> None:
        """Pop one definition key from the active stack."""
        if not self._stack:
            raise ValueError("reference stack is empty")
        definition_key = self._stack.pop()
        _ = self._stack_index.pop(definition_key)

    def cycle_for(self, definition_key: str) -> list[str] | None:
        """Return the cycle closed by this key, or None if it is not a back-edge."""
        cycle_start = self._stack_index.get(definition_key)
        if cycle_start is None:
            return None
        return [*self._stack[cycle_start:], definition_key]


class Validator:
    """Validates a single Define program."""

    def __init__(self):
        """Initialize state for validating exactly one program per Validator instance."""
        self._path_tracker: path_tracker.PathTracker[ValidationResult] = (
            path_tracker.PathTracker()
        )
        self._seen_global_definitions: dict[str, ast.QualityDefinition] = {}
        self._reference_stack: _ReferenceStack = _ReferenceStack()
        self._validation_frames: list[_ValidationFrame] = []

    @cached_property
    def _parser(self) -> parser.Parser:
        """Parser instance, created only when file parsing is needed."""
        return parser.Parser()

    def parse_and_validate_program(
        self,
        path: pathlib.PurePosixPath,
    ) -> list[ValidationResult]:
        """Parse, transform, and validate all reached files from one entrypoint."""
        self._parse_validate_and_collect(path)
        return self._path_tracker.completed_results()

    # Much of this method's behavior is intentionally exercised only through
    # Driver tests so the end-to-end filesystem/context behavior is verified
    # in one place.
    def _parse_and_validate_file(
        self,
        path: pathlib.PurePosixPath,
        root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT,
        expected_fqun: str | None = None,
    ) -> ValidationResult:
        """Parse, transform, and validate one Define file."""
        full_path = root_prefix / path
        run = _ValidationRun(file_path=full_path, stats=stats.ValidationStatsTracker())

        try:
            loaded_fqun = self._load_root_config_if_not_loaded(
                root_prefix, expected_fqun
            )
        except exceptions.ConfigError as e:
            run.stats.mark_config_loading_finished()
            return run.incomplete(e)
        run.stats.mark_config_loading_finished()

        source, syntax_error = self._load_file(full_path)
        if syntax_error is not None:
            run.stats.mark_file_loading_finished()
            return run.incomplete(syntax_error)
        run.stats.mark_file_loading_finished()
        run.source = source

        try:
            tree = self._parser.parse(source, file_path=full_path)
        except SYNTAX_ERROR_TYPES as e:
            run.stats.mark_parse_finished()
            return run.incomplete(e)
        run.stats.mark_parse_finished()

        try:
            program = transformer.DefineTransformer().transform(tree)
        except lark_exceptions.VisitError as e:
            # Lark wraps exceptions raised inside transformer callbacks.
            if isinstance(e.orig_exc, SYNTAX_ERROR_TYPES):
                run.stats.mark_transform_finished()
                return run.incomplete(e.orig_exc)
            raise
        run.stats.mark_transform_finished()

        expected_definition_path = path.with_suffix("")
        validation_diagnostics = self._validate_file_definitions(
            program=program,
            expected_definition_path=expected_definition_path,
            expected_fqun=loaded_fqun,
            root_prefix=root_prefix,
        )
        return run.complete(validation_diagnostics)

    def _parse_validate_and_collect(
        self,
        path: pathlib.PurePosixPath,
        root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT,
        expected_fqun: str | None = None,
    ) -> None:
        """Parse/validate one file once and append its result in encounter order."""
        full_path = root_prefix / path
        if self._path_tracker.is_tracked(full_path):
            return
        self._path_tracker.mark_in_progress(full_path)
        result = self._parse_and_validate_file(path, root_prefix, expected_fqun)
        self._path_tracker.set_result(full_path, result)

    def _load_file(
        self,
        path: pathlib.PurePosixPath,
    ) -> tuple[str, AnyValidationException | None]:
        """Load a Define source file and return source and syntax errors."""
        try:
            # We have to do pathlib.Path here in case we are converting
            # from a POSIX path to a Windows path.
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

    def validate(
        self,
        program: ast.Program,
        expected_definition_path: pathlib.PurePosixPath | None = None,
        # TODO: Rename this to expected_fqun.
        expected_universe_name: str | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Validate all semantic rules and return collected diagnostics.

        Args:
            expected_definition_path: Optional expected definition path, relative
                to project root, without the .def extension. When provided, the
                validator validates that definition paths match this path.
            expected_universe_name: Optional FQUN string from the project config.
                When provided, validates that each definition's FQUN matches
                this value.
        """
        return self._validate_file_definitions(
            program=program,
            expected_definition_path=expected_definition_path,
            expected_fqun=expected_universe_name,
        )

    def _validate_file_definitions(
        self,
        program: ast.Program,
        expected_definition_path: pathlib.PurePosixPath | None = None,
        expected_fqun: str | None = None,
        root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT,
    ) -> list[diagnostics.Diagnostic]:
        """Validate definitions in one file with the given root context."""
        frame = _ValidationFrame(
            diagnostics=[],
            expected_definition_path=expected_definition_path,
            root_prefix=root_prefix,
        )
        self._validation_frames.append(frame)
        try:
            for definition in program.definitions:
                self._validate_definition(definition, expected_fqun)
            return frame.diagnostics
        finally:
            _ = self._validation_frames.pop()

    @property
    def _frame(self) -> _ValidationFrame:
        """Return the current validation frame."""
        if not self._validation_frames:
            raise ValueError("Validation frame stack is empty.")
        return self._validation_frames[-1]

    @property
    def _diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return diagnostics list for the current validation frame."""
        return self._frame.diagnostics

    def _validate_definition(
        self, definition: ast.QualityDefinition, expected_fqun: str | None
    ) -> None:
        """Validate a quality definition."""
        self._diagnostics.extend(name_validators.validate_global_name(definition.name))
        self._validate_path_matches_file(definition)
        self._validate_fqun_matches_expected(definition, expected_fqun)
        self._validate_not_duplicate(definition)
        if (
            isinstance(definition, ast.ActionDefinition)
            and definition.definition_block is not None
        ):
            self._validate_local_names(definition.definition_block)
            self._validate_action_position_constraints(
                definition.definition_block,
                definition,
            )
        if isinstance(definition, ast.PositionDefinition) and definition.constraints:
            self._validate_position_constraints(
                definition.constraints,
                definition,
            )

    def _validate_path_matches_file(self, definition: ast.QualityDefinition) -> None:
        """Validate that the definition's path matches the file path."""
        expected_definition_path = self._frame.expected_definition_path
        if expected_definition_path is None:
            return

        definition_path = definition.name.path.name
        expected_path = "/" + expected_definition_path.as_posix()

        if definition_path != expected_path:
            self._diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    position=definition.name.path.position,
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_not_duplicate(self, definition: ast.QualityDefinition) -> None:
        """Validate that this definition is not a duplicate of a previous one."""
        key = definition.fully_qualified_typed_name
        if key in self._seen_global_definitions:
            first_def = self._seen_global_definitions[key]
            def_type = definition.type_name.value
            path_str = definition.name.path.name
            self._diagnostics.append(
                diagnostics.DuplicateDefinitionDiagnostic(
                    position=definition.position,
                    definition_type=def_type,
                    path=path_str,
                    first_definition_line=first_def.position.line,
                )
            )
        else:
            self._seen_global_definitions[key] = definition

    def _validate_local_names(
        self, definition_block: ast.ActionDefinitionBlock
    ) -> None:
        """Validate that local definitions have no name conflicts in local scopes."""
        outer_scope: ChainMap[str, ast.LocalPositionDefinition] = ChainMap({})
        for local_def in definition_block.local_definitions:
            self._validate_local_name_format_and_conflicts(local_def, outer_scope)

        action_statements_scope = outer_scope.new_child({})
        for local_def in definition_block.action_statements.statements:
            self._validate_local_name_format_and_conflicts(
                local_def, action_statements_scope
            )

    def _validate_local_name_format_and_conflicts(
        self,
        local_def: ast.LocalPositionDefinition,
        scope: ChainMap[str, ast.LocalPositionDefinition],
    ) -> None:
        """Validate local name formatting and scope conflicts for one definition."""
        self._diagnostics.extend(name_validators.validate_local_name_format(local_def))
        name = local_def.local_name.name
        if name in scope:
            first_def = scope[name]
            self._diagnostics.append(
                diagnostics.LocalNameConflictDiagnostic(
                    position=local_def.local_name.position,
                    local_name=name,
                    first_definition_line=first_def.local_name.position.line,
                )
            )
            return
        scope.maps[0][name] = local_def

    def _load_root_config_if_not_loaded(
        self,
        root_prefix: pathlib.PurePosixPath = constants.PROJECT_ROOT,
        expected_fqun: str | None = None,
    ) -> str:
        """Load project config for root_prefix and register it if not already done.

        Returns the FQUN string for the root.

        Raises ConfigError if the config cannot be loaded or the FQUN
        doesn't match expected_fqun.
        """
        existing = self._path_tracker.fqun_for_root(root_prefix)
        if existing is not None:
            if expected_fqun is not None and existing != expected_fqun:
                raise exceptions.SubRootFqunMismatchError(
                    expected_fqun=expected_fqun,
                    actual_fqun=existing,
                    sub_root_path=str(root_prefix),
                )
            return existing
        loader = config.ConfigLoader(root_prefix)
        loader.assert_is_project_root()
        project_config = loader.project_config()
        # TODO: This could possibly be done lazily.
        universe_locations = loader.local_deps_config()
        fqun = project_config.project.universe_name or ""
        if expected_fqun is not None and fqun != expected_fqun:
            raise exceptions.SubRootFqunMismatchError(
                expected_fqun=expected_fqun,
                actual_fqun=fqun,
                sub_root_path=str(root_prefix),
            )
        self._path_tracker.register_project_root(
            root_prefix,
            fqun,
            universe_locations,
        )
        return fqun

    def _validate_fqun_matches_expected(
        self, definition: ast.QualityDefinition, expected_fqun: str | None
    ) -> None:
        """Validate that the definition's FQUN matches the expected project FQUN."""
        if expected_fqun is None:
            return

        actual = definition.name.fqun.canonical
        if actual != expected_fqun:
            self._diagnostics.append(
                diagnostics.FqunMismatchDiagnostic(
                    position=definition.name.fqun.position,
                    expected=expected_fqun,
                    actual=actual,
                )
            )

    def _validate_action_position_constraints(
        self,
        definition_block: ast.ActionDefinitionBlock,
        enclosing_definition: ast.QualityDefinition,
    ) -> None:
        """Validate constraints inside local position definitions in an action."""
        for local_def in definition_block.local_definitions:
            if local_def.constraints is not None:
                self._validate_position_constraints(
                    local_def.constraints,
                    enclosing_definition,
                )
        for local_def in definition_block.action_statements.statements:
            if local_def.constraints is not None:
                self._validate_position_constraints(
                    local_def.constraints,
                    enclosing_definition,
                )

    def _validate_position_constraints(
        self,
        constraints: ast.PositionConstraintBlock,
        enclosing_definition: ast.QualityDefinition,
    ) -> None:
        """Validate names and short-form usage in position constraints."""
        enclosing_fqun = enclosing_definition.name.fqun

        for requirement in constraints.requirements:
            reference = requirement.typed_global_name.global_name
            reference_diagnostics = name_validators.validate_global_name(
                reference, must_use_short_form=enclosing_fqun
            )
            self._diagnostics.extend(reference_diagnostics)
            if reference_diagnostics:
                continue
            self._load_global_name_reference(
                typed_global_name=requirement.typed_global_name,
                enclosing_definition=enclosing_definition,
            )

    def _load_global_name_reference(
        self,
        typed_global_name: ast.TypedGlobalNameReference,
        enclosing_definition: ast.QualityDefinition,
    ):
        """Load and validate one global name reference."""
        self._reference_stack.push(enclosing_definition)
        self._do_load_global_name_reference(typed_global_name, enclosing_definition)
        self._reference_stack.pop()

    def _do_load_global_name_reference(
        self,
        typed_global_name: ast.TypedGlobalNameReference,
        enclosing_definition: ast.QualityDefinition,
    ):
        """Load and validate one global name reference with stack already set."""
        if typed_global_name.global_name.fqun is None:
            typed_name_str = typed_global_name.fully_qualified_typed_name(
                with_fqun=enclosing_definition.name.fqun,
            )
        else:
            typed_name_str = typed_global_name.fully_qualified_typed_name()

        diagnostic = self._check_cycle(typed_global_name, typed_name_str)
        if diagnostic:
            self._diagnostics.append(diagnostic)
            return

        global_name = typed_global_name.global_name
        if global_name.fqun is not None:
            if self._path_tracker.is_unknown_universe(global_name.fqun.canonical):
                return
            diagnostic = self._check_sub_root_configured(
                global_name.fqun, enclosing_definition
            )
            if diagnostic:
                self._path_tracker.mark_unknown_universe(global_name.fqun.canonical)
                self._diagnostics.append(diagnostic)
                return
            self._walk_into_sub_root(typed_global_name, typed_name_str)
            return

        enclosing_fqun = enclosing_definition.name.fqun
        self._walk_in_current_root(
            typed_global_name, typed_name_str, enclosing_fqun.canonical
        )

    def _walk_in_current_root(
        self,
        typed_global_name: ast.TypedGlobalNameReference,
        typed_name_str: str,
        expected_fqun: str,
    ):
        """Resolve a same-FQUN reference within the current root."""
        full_file_path = typed_global_name.global_name.path.file_path(
            self._frame.root_prefix
        )

        # Check if a sub-root has already claimed this path.
        enclosing_root = self._path_tracker.find_enclosing_root(full_file_path)
        if enclosing_root != self._frame.root_prefix:
            self._diagnostics.append(
                diagnostics.PathInsideOtherUniverseDiagnostic(
                    position=typed_global_name.global_name.position,
                    path=str(full_file_path),
                    other_universe=self._path_tracker.fqun_for_root(enclosing_root)
                    or "",
                    sub_root_path=str(enclosing_root),
                )
            )
            return

        self._load_and_check_reference(
            root_prefix=self._frame.root_prefix,
            expected_fqun=expected_fqun,
            typed_global_name=typed_global_name,
            typed_name_str=typed_name_str,
        )

    def _walk_into_sub_root(
        self,
        typed_global_name: ast.TypedGlobalNameReference,
        typed_name_str: str,
    ):
        """Walk into a configured sub-root to resolve a cross-FQUN reference."""
        fqun = typed_global_name.global_name.fqun
        if fqun is None:
            raise ValueError("_walk_into_sub_root requires a non-None fqun")
        fqun_string = fqun.canonical
        universe_location = self._path_tracker.sub_root_location(
            fqun_string, self._frame.root_prefix
        )
        sub_root_path = self._frame.root_prefix / universe_location

        # The first time we load a sub-root, we need to make sure no other
        # files were loaded under that path already.
        if not self._path_tracker.project_root_loaded(sub_root_path):
            conflicting_path, existing_universe = (
                self._path_tracker.first_tracked_file_under(sub_root_path)
            )
            if conflicting_path is not None:
                # We don't stop processing after this diagnostic, because there's
                # nothing actually preventing us from continuing validation.
                self._diagnostics.append(
                    diagnostics.SubRootAlreadyOccupiedDiagnostic(
                        position=fqun.position,
                        universe=fqun_string,
                        sub_root_path=str(sub_root_path),
                        existing_file=str(conflicting_path),
                        existing_universe=existing_universe or "",
                    )
                )

        self._load_and_check_reference(
            root_prefix=sub_root_path,
            expected_fqun=fqun_string,
            typed_global_name=typed_global_name,
            typed_name_str=typed_name_str,
        )

    def _load_and_check_reference(
        self,
        root_prefix: pathlib.PurePosixPath,
        expected_fqun: str,
        typed_global_name: ast.TypedGlobalNameReference,
        typed_name_str: str,
    ):
        """Load a referenced file and check for not-found and wrong-type errors."""
        global_name = typed_global_name.global_name
        full_file_path = global_name.path.file_path(root_prefix)
        self._parse_validate_and_collect(
            global_name.path.file_path(),
            root_prefix=root_prefix,
            expected_fqun=expected_fqun,
        )

        config_diagnostic = self._check_config_error(global_name, full_file_path)
        if config_diagnostic is not None:
            self._path_tracker.mark_not_found(full_file_path)
            self._path_tracker.mark_unknown_universe(expected_fqun)
            self._diagnostics.append(config_diagnostic)
            return

        diagnostic = self._check_file_not_found(global_name, full_file_path)
        if diagnostic is not None:
            self._path_tracker.mark_not_found(full_file_path)
            self._diagnostics.append(diagnostic)
            return

        if typed_name_str not in self._seen_global_definitions:
            self._diagnostics.append(
                diagnostics.ReferencedGlobalNameWrongTypeDiagnostic(
                    position=global_name.position,
                    path=global_name.path.name,
                    expected_type=typed_global_name.type_name.value,
                )
            )

    def _check_config_error(
        self,
        global_name: ast.GlobalNameReference,
        full_file_path: pathlib.PurePosixPath,
    ) -> diagnostics.ConfigLoadErrorDiagnostic | None:
        """Check if the referenced file failed due to a config error in its root."""
        referenced_result = self._path_tracker.get_result(full_file_path)
        if isinstance(referenced_result.exception, exceptions.ConfigError):
            return diagnostics.ConfigLoadErrorDiagnostic(
                position=global_name.position,
                error=referenced_result.exception,
            )
        return None

    def _check_file_not_found(
        self, reference: ast.GlobalNameReference, referenced_file: pathlib.PurePosixPath
    ) -> diagnostics.ReferencedFileNotFoundDiagnostic | None:
        referenced_result = self._path_tracker.get_result(referenced_file)
        if isinstance(referenced_result.exception, exceptions.SourceFileNotFoundError):
            return diagnostics.ReferencedFileNotFoundDiagnostic(
                position=reference.position,
                file_path=str(referenced_file),
            )
        return None

    def _check_cycle(
        self,
        typed_global_name: ast.TypedGlobalNameReference,
        typed_name_str: str,
    ) -> diagnostics.CircularGlobalReferenceDiagnostic | None:
        cycle = self._reference_stack.cycle_for(typed_name_str)
        if cycle is not None:
            return diagnostics.CircularGlobalReferenceDiagnostic(
                position=typed_global_name.position,
                cycle=cycle,
            )
        return None

    def _check_sub_root_configured(
        self,
        fqun: ast.Fqun,
        enclosing_definition: ast.QualityDefinition,
    ) -> diagnostics.Diagnostic | None:
        fqun_string = fqun.canonical
        enclosing_fqun = enclosing_definition.name.fqun
        current_universe = enclosing_fqun.canonical
        try:
            # TODO: This should return a Config object, and that's what we
            # should store in path_tracker. Then we can delete
            # universe_has_sub_root_in.
            _ = self._load_root_config_if_not_loaded(
                self._frame.root_prefix, expected_fqun=current_universe
            )
        except exceptions.NotProjectRootError as e:
            return diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                position=fqun.position,
                universe=fqun_string,
                # TODO: This will stringify incorrectly on Windows.
                config_path=str(e.config_path),
            )
        except exceptions.ConfigError as e:
            return diagnostics.ConfigLoadErrorDiagnostic(
                position=fqun.position,
                error=e,
            )
        if not self._path_tracker.universe_has_sub_root_in(
            fqun_string, self._frame.root_prefix
        ):
            return diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                position=fqun.position,
                universe=fqun_string,
                current_universe_name=current_universe,
            )
        return None
