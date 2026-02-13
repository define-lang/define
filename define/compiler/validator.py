"""Semantic validation for the Define language AST."""

from __future__ import annotations

from collections import ChainMap
from functools import cached_property

from define.compiler import ast, diagnostics, name_validators


class Validator:
    """Validates semantic rules for a Define program AST."""

    _program: ast.Program
    _source: str

    def __init__(self, program: ast.Program, source: str):
        """Initialize validator with a program AST and source code."""
        self._program = program
        self._source = source
        self._diagnostics: list[diagnostics.Diagnostic] = []
        self._seen_definitions: dict[
            tuple[ast.TypeName, str], ast.QualityDefinition
        ] = {}

    @cached_property
    def source_lines(self) -> list[str]:
        """Source code split into lines, for use with diagnostics.Diagnostic.format()."""
        return self._source.splitlines()

    def validate(
        self,
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
        self._seen_definitions = {}
        for definition in self._program.definitions:
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

    def _validate_path_matches_file(
        self, definition: ast.QualityDefinition, file_path: str | None
    ) -> None:
        """Validate that the definition's path matches the file path."""
        if file_path is None:
            return

        definition_path = definition.name.path.path_string
        expected_path = "/" + file_path

        if definition_path != expected_path:
            self._diagnostics.append(
                diagnostics.PathMismatchDiagnostic(
                    position=definition.name.position,
                    message=(
                        f"definition path '{definition_path}' does not match "
                        f"file path '{expected_path}'"
                    ),
                    expected_path=expected_path,
                    actual_path=definition_path,
                )
            )

    def _validate_not_duplicate(self, definition: ast.QualityDefinition) -> None:
        """Validate that this definition is not a duplicate of a previous one."""
        key = (definition.type_name, definition.name.path.path_string)
        if key in self._seen_definitions:
            first_def = self._seen_definitions[key]
            def_type = definition.type_name.value
            path_str = definition.name.path.path_string
            self._diagnostics.append(
                diagnostics.DuplicateDefinitionDiagnostic(
                    position=definition.position,
                    message=(
                        f"duplicate {def_type} definition for path '{path_str}'; "
                        f"first defined on line {first_def.position.line}"
                    ),
                    definition_type=def_type,
                    path=path_str,
                    first_definition_line=first_def.position.line,
                )
            )
        else:
            self._seen_definitions[key] = definition

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
                    message=(
                        f"duplicate local definition '{name}'; "
                        f"first defined on line {first_def.local_name.position.line}"
                    ),
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
                    message=(
                        f"Fully-qualified universe name '{actual}' does not match project "
                        f"universe name '{expected_universe_name}'"
                    ),
                    expected=expected_universe_name,
                    actual=actual,
                )
            )
