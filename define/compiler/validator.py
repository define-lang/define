"""Semantic validation for the Define language AST."""

from __future__ import annotations

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
        self._seen_definitions: dict[tuple[type, str], ast.QualityDefinition] = {}

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
        self._validate_global_name(definition.name)
        self._validate_path_matches_file(definition, file_path)
        self._validate_fqun_matches_expected(definition, expected_universe_name)
        self._validate_not_duplicate(definition)
        if (
            isinstance(definition, ast.ActionDefinition)
            and definition.definition_block is not None
        ):
            for local_def in definition.definition_block.local_definitions:
                self._diagnostics.extend(
                    name_validators.validate_local_name_format(local_def)
                )

    def _validate_global_name(self, name: ast.GlobalName) -> None:
        """Validate a global name and its FQUN."""
        self._validate_fqun(name.fqun)
        self._diagnostics.extend(name_validators.validate_global_name_path(name.path))

    def _validate_fqun(self, fqun: ast.Fqun) -> None:
        """Validate a fully-qualified universe name."""
        if fqun.multiverse is not None:
            self._diagnostics.extend(
                name_validators.validate_multiverse_name_format(fqun.multiverse)
            )
            self._diagnostics.extend(
                name_validators.validate_multiverse_name_reserved(fqun.multiverse)
            )

        if fqun.authority is None:
            if fqun.universe.name.lower() != "standard":
                self._diagnostics.append(
                    diagnostics.UniverseWithoutAuthorityDiagnostic(
                        position=fqun.universe.position,
                        message=(
                            f"universe '{fqun.universe.name}' requires an authority; "
                            f"only 'standard' may be used without an authority"
                        ),
                        universe_name=fqun.universe.name,
                    )
                )
        else:
            self._diagnostics.extend(
                name_validators.validate_authority_domain_format(fqun.authority)
            )
            self._diagnostics.extend(
                name_validators.validate_authority_path_format(fqun.authority)
            )
            self._diagnostics.extend(
                name_validators.validate_authority_reserved(
                    fqun.authority, fqun.multiverse
                )
            )

        self._diagnostics.extend(
            name_validators.validate_universe_name_format(fqun.universe)
        )
        self._diagnostics.extend(
            name_validators.validate_universe_name_reserved(fqun.universe)
        )

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
        key = (type(definition), definition.name.path.path_string)
        if key in self._seen_definitions:
            first_def = self._seen_definitions[key]
            match definition:
                case ast.PositionDefinition():
                    def_type = "position"
                case ast.ActionDefinition():
                    def_type = "action"
                case _:
                    raise TypeError(f"Unknown definition type: {type(definition)}")
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

    def _validate_fqun_matches_expected(
        self,
        definition: ast.QualityDefinition,
        expected_universe_name: str | None,
    ) -> None:
        """Validate that the definition's FQUN matches the expected project FQUN."""
        if expected_universe_name is None:
            return

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
