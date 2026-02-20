"""Semantic validation for the Define language AST."""

from __future__ import annotations

import pathlib
import time
from collections import ChainMap, OrderedDict
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

from lark import exceptions as lark_exceptions

from define.compiler import (
    ast,
    config,
    diagnostics,
    exceptions,
    name_validators,
    parser,
    parser_error_classification,
    parser_exceptions,
    transformer,
)

type AnyValidationException = exceptions.DefineError | lark_exceptions.UnexpectedInput
SYNTAX_ERROR_TYPES = (
    parser_exceptions.DefineSyntaxError,
    lark_exceptions.UnexpectedInput,
)


def _config_error_result(
    path: pathlib.PurePosixPath,
    error: AnyValidationException,
) -> ValidationResult:
    return ValidationResult(
        diagnostics=[],
        exception=error,
        source=None,
        file_path=path,
        stats=ValidationTimingStats(overall=0, parse=0, transform=None, validate=None),
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
class ValidationTimingStats:
    """Timing measurements for parse/transform/validate steps."""

    overall: int
    parse: int
    transform: int | None
    validate: int | None


@dataclass
class _ValidationRun:
    """Tracks a single parse/validate run and builds consistent results."""

    file_path: pathlib.PurePosixPath
    started_at: int
    source: str | None = None
    parse_finished_at: int | None = None
    transform_finished_at: int | None = None

    def mark_parse_finished(self) -> None:
        self.parse_finished_at = time.perf_counter_ns()

    def mark_transform_finished(self) -> None:
        self.transform_finished_at = time.perf_counter_ns()

    def incomplete(
        self,
        syntax_error: AnyValidationException,
    ) -> ValidationResult:
        if self.parse_finished_at is None:
            raise ValueError("Parse timing was not recorded before syntax failure.")
        parse_elapsed = self.parse_finished_at - self.started_at
        if self.transform_finished_at is None:
            overall_elapsed = parse_elapsed
            transform_elapsed: int | None = None
        else:
            transform_elapsed = self.transform_finished_at - self.parse_finished_at
            overall_elapsed = self.transform_finished_at - self.started_at
        return ValidationResult(
            diagnostics=[],
            exception=syntax_error,
            source=self.source,
            file_path=self.file_path,
            stats=ValidationTimingStats(
                overall=overall_elapsed,
                parse=parse_elapsed,
                transform=transform_elapsed,
                validate=None,
            ),
        )

    def complete(
        self, diagnostics_list: list[diagnostics.Diagnostic]
    ) -> ValidationResult:
        if self.parse_finished_at is None:
            raise ValueError("Parse timing was not recorded before success.")
        if self.transform_finished_at is None:
            raise ValueError("Transform timing was not recorded before success.")
        if self.source is None:
            raise ValueError("Source text was not recorded before success.")
        validate_finished_at = time.perf_counter_ns()
        return ValidationResult(
            diagnostics=diagnostics_list,
            exception=None,
            source=self.source,
            file_path=self.file_path,
            stats=ValidationTimingStats(
                overall=validate_finished_at - self.started_at,
                parse=self.parse_finished_at - self.started_at,
                transform=self.transform_finished_at - self.parse_finished_at,
                validate=validate_finished_at - self.transform_finished_at,
            ),
        )


@dataclass
class _ValidationFrame:
    """Per-file validation context used by the validator call stack."""

    diagnostics: list[diagnostics.Diagnostic]
    expected_definition_path: pathlib.PurePosixPath | None
    expected_universe_name: str | None
    universe_locations: Mapping[str, pathlib.PurePosixPath]


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
        self.results_by_path: OrderedDict[
            pathlib.PurePosixPath, ValidationResult | None
        ] = OrderedDict()
        self._seen_global_definitions: dict[str, ast.QualityDefinition] = {}
        self._reference_stack: _ReferenceStack = _ReferenceStack()
        self._validation_frames: list[_ValidationFrame] = []
        self._reference_not_found_paths: set[pathlib.PurePosixPath] = set()
        self._unknown_universes: set[str] = set()

    @cached_property
    def _parser(self) -> parser.Parser:
        """Parser instance, created only when file parsing is needed."""
        return parser.Parser()

    def parse_and_validate_program(
        self,
        path: pathlib.PurePosixPath,
    ) -> list[ValidationResult]:
        """Parse, transform, and validate all reached files from one entrypoint."""
        try:
            config.assert_is_project_root()
            project_config = config.project_config()
            universe_locations = config.local_deps_config()
        except exceptions.DefineError as e:
            return [_config_error_result(path, e)]
        self._parse_validate_and_collect(
            path,
            project_config.project.universe_name or "",
            universe_locations,
        )
        return [
            result
            for result in self.results_by_path.values()
            if result is not None
            and result.file_path not in self._reference_not_found_paths
        ]

    # Much of this method's behavior is intentionally exercised only through
    # Driver tests so the end-to-end filesystem/context behavior is verified
    # in one place.
    def _parse_and_validate_file(
        self,
        path: pathlib.PurePosixPath,
        expected_universe_name: str | None,
        universe_locations: Mapping[str, pathlib.PurePosixPath],
    ) -> ValidationResult:
        """Parse, transform, and validate one Define file."""
        run = _ValidationRun(file_path=path, started_at=time.perf_counter_ns())

        source, syntax_error = self._load_file(path)
        if syntax_error is not None:
            run.mark_parse_finished()
            return run.incomplete(syntax_error)
        run.source = source

        try:
            tree = self._parser.parse(source, file_path=path)
        except SYNTAX_ERROR_TYPES as e:
            run.mark_parse_finished()
            return run.incomplete(e)
        run.mark_parse_finished()

        try:
            program = transformer.DefineTransformer().transform(tree)
        except lark_exceptions.VisitError as e:
            # Lark wraps exceptions raised inside transformer callbacks.
            if isinstance(e.orig_exc, SYNTAX_ERROR_TYPES):
                run.mark_transform_finished()
                return run.incomplete(e.orig_exc)
            raise
        run.mark_transform_finished()

        expected_definition_path = path.with_suffix("")
        validation_diagnostics = self.validate(
            program=program,
            expected_definition_path=expected_definition_path,
            expected_universe_name=expected_universe_name,
            universe_locations=universe_locations,
        )
        return run.complete(validation_diagnostics)

    def _parse_validate_and_collect(
        self,
        path: pathlib.PurePosixPath,
        expected_universe_name: str | None,
        universe_locations: Mapping[str, pathlib.PurePosixPath],
    ) -> None:
        """Parse/validate one file once and append its result in encounter order."""
        if path in self.results_by_path:
            return
        self.results_by_path[path] = None
        result = self._parse_and_validate_file(
            path=path,
            expected_universe_name=expected_universe_name,
            universe_locations=universe_locations,
        )
        self.results_by_path[path] = result

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
        expected_universe_name: str | None = None,
        universe_locations: Mapping[str, pathlib.PurePosixPath] | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Validate all semantic rules and return collected diagnostics.

        Args:
            expected_definition_path: Optional expected definition path, relative
                to project root, without the .def extension. When provided, the
                validator operates in filesystem context and validates that
                definition paths match this path. When None, the validator
                operates in non-filesystem context and skips path matching
                validation.
            expected_universe_name: Optional FQUN string from the project config.
                When provided, validates that each definition's FQUN matches this
                value. When None, skips FQUN matching validation.
            universe_locations: Mapping from universe name to local path for
                configured external dependencies. Defaults to no configured
                dependencies.
        """
        frame = _ValidationFrame(
            diagnostics=[],
            expected_definition_path=expected_definition_path,
            expected_universe_name=expected_universe_name,
            universe_locations=universe_locations
            if universe_locations is not None
            else {},
        )
        self._validation_frames.append(frame)
        try:
            for definition in program.definitions:
                self._validate_definition(definition)
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

    def _validate_definition(self, definition: ast.QualityDefinition) -> None:
        """Validate a quality definition."""
        self._diagnostics.extend(name_validators.validate_global_name(definition.name))
        self._validate_path_matches_file(definition)
        self._validate_fqun_matches_expected(definition)
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

    def _validate_fqun_matches_expected(
        self, definition: ast.QualityDefinition
    ) -> None:
        """Validate that the definition's FQUN matches the expected project FQUN."""
        expected_universe_name = self._frame.expected_universe_name
        if expected_universe_name is None:
            return

        # Narrow fqun for pyright; GlobalNameDefinition always has a non-None fqun.
        if definition.name.fqun is None:
            raise ValueError("GlobalNameDefinition must have a non-None fqun")

        actual = definition.name.fqun.canonical
        if actual != expected_universe_name:
            self._diagnostics.append(
                diagnostics.FqunMismatchDiagnostic(
                    position=definition.name.fqun.position,
                    expected=expected_universe_name,
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

        reference = typed_global_name.global_name
        if reference.fqun is not None:
            if reference.fqun.canonical in self._unknown_universes:
                return
            diagnostic = self._check_sub_root_configured(reference.fqun)
            if diagnostic:
                self._unknown_universes.add(reference.fqun.canonical)
                self._diagnostics.append(diagnostic)
                return
            raise NotImplementedError(
                "Global-reference file walking for FQUN references is not implemented."
            )

        referenced_file = reference.path.relative_path.with_suffix(".def")

        self._parse_validate_and_collect(
            path=referenced_file,
            expected_universe_name=self._frame.expected_universe_name,
            universe_locations=self._frame.universe_locations,
        )

        diagnostic = self._check_file_not_found(reference, referenced_file)
        if diagnostic is not None:
            self._reference_not_found_paths.add(referenced_file)
            self._diagnostics.append(diagnostic)
            return

        if typed_name_str not in self._seen_global_definitions:
            self._diagnostics.append(
                diagnostics.ReferencedGlobalNameWrongTypeDiagnostic(
                    position=reference.position,
                    path=reference.path.name,
                    expected_type=typed_global_name.type_name.value,
                )
            )

    def _check_file_not_found(
        self, reference: ast.GlobalNameReference, referenced_file: pathlib.PurePosixPath
    ) -> diagnostics.ReferencedFileNotFoundDiagnostic | None:
        referenced_result = self.results_by_path[referenced_file]
        if referenced_result is None or referenced_result.exception is not None:
            if referenced_result is not None and isinstance(
                referenced_result.exception, exceptions.SourceFileNotFoundError
            ):
                return diagnostics.ReferencedFileNotFoundDiagnostic(
                    position=reference.position,
                    file_path=str(referenced_file),
                )
            return None
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
        self, fqun: ast.Fqun
    ) -> diagnostics.ExternalUniverseNotConfiguredDiagnostic | None:
        fqun_string = fqun.canonical
        if fqun_string not in self._frame.universe_locations:
            expected = self._frame.expected_universe_name
            if expected is None:
                raise ValueError(
                    "expected_universe_name must be set for cross-universe references"
                )
            return diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                position=fqun.position,
                universe=fqun_string,
                current_universe_name=expected,
            )
        return None
