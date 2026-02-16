"""Semantic validation for the Define language AST."""

from __future__ import annotations

import time
from collections import ChainMap
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from lark import exceptions as lark_exceptions

if TYPE_CHECKING:
    from pathlib import Path

from define.compiler import (
    ast,
    diagnostics,
    name_validators,
    parser,
    transformer,
)


@dataclass
class ValidationResult:
    """Validation output for one source file."""

    diagnostics: list[diagnostics.Diagnostic]
    source: str
    stats: list[ValidationFileStats]


@dataclass
class ValidationTimingStats:
    """Timing measurements for parse/transform/validate steps."""

    overall: int
    parse: int
    transform: int
    validate: int


@dataclass
class ValidationFileStats:
    """Validation stats for one file."""

    path: Path
    timings: ValidationTimingStats


class Validator:
    """Validates semantic rules for a Define program AST."""

    def __init__(self):
        """Initialize validator state."""
        self._diagnostics: list[diagnostics.Diagnostic] = []
        self._seen_global_definitions: dict[
            tuple[ast.TypeName, str], ast.QualityDefinition
        ] = {}

    @cached_property
    def _parser(self) -> parser.Parser:
        """Parser instance, created only when file parsing is needed."""
        return parser.Parser()

    # This method is intentionally exercised primarily through Driver tests so
    # the end-to-end filesystem/context behavior is verified in one place.
    def parse_and_validate_file(
        self,
        path: Path,
        expected_universe_name: str | None = None,
    ) -> ValidationResult:
        """Parse, transform, and validate one Define file."""
        overall_start = time.perf_counter_ns()
        tree, source = self._parser.parse_file(path)
        after_parse = time.perf_counter_ns()
        try:
            program = transformer.DefineTransformer().transform(tree)
        except lark_exceptions.VisitError as e:
            # Lark wraps exceptions raised inside transformer callbacks.
            raise e.orig_exc from e
        after_transform = time.perf_counter_ns()
        file_path = path.with_suffix("").as_posix()
        result = self.validate(
            program=program,
            file_path=file_path,
            expected_universe_name=expected_universe_name,
        )
        after_validate = time.perf_counter_ns()
        timings = ValidationTimingStats(
            overall=after_validate - overall_start,
            parse=after_parse - overall_start,
            transform=after_transform - after_parse,
            validate=after_validate - after_transform,
        )
        file_stats = ValidationFileStats(path=path, timings=timings)
        return ValidationResult(diagnostics=result, source=source, stats=[file_stats])

    def validate(
        self,
        program: ast.Program,
        file_path: str | None = None,
        expected_universe_name: str | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Validate all semantic rules and return collected diagnostics.

        Args:
            file_path: Optional path to the source file, relative to project root,
                without the .def extension. When provided, the validator operates
                in filesystem context and validates that definition paths match
                the file path. When None, the validator operates in non-filesystem
                context and skips path matching validation.
            expected_universe_name: Optional FQUN string from the project config.
                When provided, validates that each definition's FQUN matches this
                value. When None, skips FQUN matching validation.
        """
        self._diagnostics = []
        self._seen_global_definitions = {}
        for definition in program.definitions:
            self._validate_definition(definition, file_path, expected_universe_name)
        return self._diagnostics

    def _validate_definition(
        self,
        definition: ast.QualityDefinition,
        file_path: str | None,
        expected_universe_name: str | None,
    ) -> None:
        """Validate a quality definition."""
        self._diagnostics.extend(name_validators.validate_global_name(definition.name))
        self._validate_path_matches_file(definition, file_path)
        self._validate_fqun_matches_expected(definition, expected_universe_name)
        self._validate_not_duplicate(definition)
        if (
            isinstance(definition, ast.ActionDefinition)
            and definition.definition_block is not None
        ):
            self._validate_local_names(definition.definition_block)
            self._validate_action_position_constraints(
                definition.definition_block,
                definition.name.fqun,
            )
        if isinstance(definition, ast.PositionDefinition) and definition.constraints:
            self._validate_position_constraints(
                definition.constraints, definition.name.fqun
            )

    def _validate_path_matches_file(
        self, definition: ast.QualityDefinition, file_path: str | None
    ) -> None:
        """Validate that the definition's path matches the file path."""
        if file_path is None:
            return

        definition_path = definition.name.path.name
        expected_path = "/" + file_path

        if definition_path != expected_path:
            self._diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    position=definition.name.position,
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_not_duplicate(self, definition: ast.QualityDefinition) -> None:
        """Validate that this definition is not a duplicate of a previous one."""
        key = (definition.type_name, definition.name.path.name)
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
        self,
        definition: ast.QualityDefinition,
        expected_universe_name: str | None,
    ) -> None:
        """Validate that the definition's FQUN matches the expected project FQUN."""
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
        enclosing_fqun: ast.Fqun | None,
    ) -> None:
        """Validate constraints inside local position definitions in an action."""
        for local_def in definition_block.local_definitions:
            if local_def.constraints is not None:
                self._validate_position_constraints(
                    local_def.constraints, enclosing_fqun
                )
        for local_def in definition_block.action_statements.statements:
            if local_def.constraints is not None:
                self._validate_position_constraints(
                    local_def.constraints, enclosing_fqun
                )

    def _validate_position_constraints(
        self, constraints: ast.PositionConstraintBlock, enclosing_fqun: ast.Fqun | None
    ) -> None:
        """Validate names and short-form usage in position constraints."""
        if enclosing_fqun is None:
            raise ValueError("Global quality definitions must have a non-None fqun")

        for requirement in constraints.requirements:
            reference = requirement.typed_global_name.global_name
            self._diagnostics.extend(
                name_validators.validate_global_name(
                    reference, must_use_short_form=enclosing_fqun
                )
            )
