"""Pure per-file and per-definition validation for the Define language.

FileStructuralValidator loads one file at a time, and a LoadedFile validates
one of its definitions at a time. Neither has access to shared mutable state
other than the source map that loaded files are registered with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics
from define.compiler.parsing import parser
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    definition_validator,
    file_validation_context,
)

if TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler.errors import syntax_errors


type FileDefinitions = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]], ast.GlobalDefinition
]


class LoadedFile(msgspec.Struct):
    """A parsed file, whose definitions are validated only when requested."""

    context: file_validation_context.FileValidationContext
    # The diagnostic that kept the file from loading or parsing, if any.
    load_failure: syntax_errors.FileLoadFailureDiagnostic | None
    file_diagnostics: list[diagnostics.Diagnostic]
    # The first definition of each typed name in the file. It does not change
    # after loading, so definitions can be validated concurrently.
    definitions: FileDefinitions

    def earlier_definition(
        self,
        reference: ast.GlobalTypedNameReference,
        referencing_definition: ast.GlobalDefinition,
    ) -> ast.GlobalDefinition | None:
        """Return the file's definition of a referenced name if it comes before the referencing definition."""
        definition = self.definitions.get(reference)
        if definition is None:
            return None
        location = definition.location
        referencing_location = referencing_definition.location
        if (location.line, location.column) < (
            referencing_location.line,
            referencing_location.column,
        ):
            return definition
        return None

    def build_file_validation_result(
        self, definition_results: list[validation_result.DefinitionValidationResult]
    ) -> validation_result.FileValidationResult:
        """Return the file's result, given the results of its validated definitions in source order."""
        return validation_result.FileValidationResult(
            load_failure=self.load_failure,
            file_path=self.context.full_path,
            root_prefix=self.context.root_prefix,
            file_diagnostics=self.file_diagnostics,
            definition_results=definition_results,
        )

    def validate_definition(
        self, definition: ast.GlobalDefinition
    ) -> validation_result.DefinitionValidationResult:
        """Validate one of the file's definitions."""
        return definition_validator.DefinitionStructuralValidator(
            definition=definition,
            context=self.context,
        ).validate_definition()


class FileStructuralValidator:
    """Per-file loader.

    Processes one file: reads from disk, registers it with a source map, parses
    it, and checks the rules that concern the file as a whole. Its definitions
    are validated separately, only when something requests them.
    """

    _source_map: rendering.SourceMap

    def __init__(self, source_map: rendering.SourceMap):
        """Initialize with the source map to register loaded files with."""
        self._source_map = source_map

    def load_file(
        self, context: file_validation_context.FileValidationContext
    ) -> LoadedFile:
        """Load and parse a single file."""
        parse_result = parser.parse_file(str(context.full_path), self._source_map)
        return self._check_file(context, parse_result)

    def load_source(self, source: str) -> LoadedFile:
        """Parse source text without loading from the filesystem."""
        parse_result = parser.parse(
            # A lone surrogate becomes invalid UTF-8, as it would be in a file,
            # instead of failing to encode.
            source.encode(errors="surrogatepass"),
            None,
            # Source that is not from the filesystem need not follow the indentation
            # rules.
            check_indentation=False,
        )
        return self._check_file(
            file_validation_context.EmptyFileValidationContext(), parse_result
        )

    @staticmethod
    def _check_file(
        context: file_validation_context.FileValidationContext,
        parse_result: parser.ParseResult,
    ) -> LoadedFile:
        """Check the rules that concern a parsed file as a whole."""
        if parse_result.load_failure is not None:
            return LoadedFile(
                context=context,
                load_failure=parse_result.load_failure,
                file_diagnostics=parse_result.diagnostics,
                definitions=typed_name_dict.TypedNameDict(),
            )

        if parse_result.program is None:
            raise ValueError(
                "parse produced no program despite reporting no syntax error"
            )
        program = parse_result.program

        file_diagnostics = parse_result.diagnostics
        definitions: FileDefinitions = typed_name_dict.TypedNameDict()
        for definition in program.definitions:
            file_diagnostics.extend(_path_mismatch_diagnostics(definition, context))
            file_diagnostics.extend(_fqun_mismatch_diagnostics(definition, context))
            first_definition = definitions.get(definition.typed_name)
            if first_definition is None:
                definitions[definition.typed_name] = definition
                continue
            file_diagnostics.append(
                diagnostics.DuplicateDefinitionDiagnostic(
                    location=definition.location,
                    definition_type=definition.typed_name.name_type.value,
                    path=definition.typed_name.name_content.path.name,
                    first_definition_line=first_definition.location.line,
                )
            )

        return LoadedFile(
            context=context,
            load_failure=None,
            file_diagnostics=file_diagnostics,
            definitions=definitions,
        )


def _path_mismatch_diagnostics(
    definition: ast.GlobalDefinition,
    context: file_validation_context.FileValidationContext,
) -> list[diagnostics.Diagnostic]:
    if context.expected_definition_path is None:
        return []
    definition_path = definition.typed_name.name_content.path.name
    expected_path = str(context.expected_definition_path.as_absolute_path())
    if definition_path == expected_path:
        return []
    return [
        diagnostics.PathMismatchDiagnostic(
            location=definition.typed_name.name_content.path.location,
            expected_path=expected_path,
            actual_path=definition_path,
        )
    ]


def _fqun_mismatch_diagnostics(
    definition: ast.GlobalDefinition,
    context: file_validation_context.FileValidationContext,
) -> list[diagnostics.Diagnostic]:
    root_config = context.root_config
    expected_fqun = "" if root_config is None else root_config.fqun
    if not expected_fqun:
        return []
    actual = definition.typed_name.name_content.fqun.canonical
    if actual == expected_fqun:
        return []
    return [
        diagnostics.FqunMismatchDiagnostic(
            location=definition.typed_name.name_content.fqun.location,
            expected=expected_fqun,
            actual=actual,
        )
    ]
