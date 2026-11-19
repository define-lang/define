"""Loading of Define source files, which checks the rules that concern a file as a whole.

load_file and load_source each load one file. Neither has access to shared
mutable state other than the source map that loaded files are registered
with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import msgspec

from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.parsing import parser
from define.compiler.validator import validation_result
from define.compiler.validator.structural import file_validation_context

if TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler import ast


class LoadedFile(msgspec.Struct):
    """A parsed file, whose definitions are validated only when requested."""

    context: file_validation_context.FileValidationContext
    # Why the file could not be read, if it could not. A reference into the
    # file reports it.
    read_failure: syntax_errors.SourceFileReadFailure | None
    # The first definition of each typed name in the file, by its full typed
    # name. It does not change after loading, so definitions can be validated
    # concurrently.
    definitions: dict[str, ast.GlobalDefinition]

    def earlier_definition(
        self,
        reference: ast.GlobalTypedNameReference,
        referencing_definition: ast.GlobalDefinition,
    ) -> ast.GlobalDefinition | None:
        """Return the file's definition of a referenced name if it comes before the referencing definition."""
        definition = self.definitions.get(reference.full_typed_name)
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
            file_path=self.context.full_path,
            root_prefix=self.context.root_prefix,
            definition_results=definition_results,
        )


def load_file(
    context: file_validation_context.FileValidationContext,
    source_map: rendering.SourceMap,
) -> tuple[LoadedFile, list[diagnostics.Diagnostic]]:
    """Read and parse one file, register it with source_map, and check the rules that concern the file as a whole, and return it and its diagnostics.

    The file's definitions are validated separately, only when something
    requests them. Why the file could not be read is not a diagnostic. The
    loaded file records it.
    """
    parse_result = parser.parse_file(str(context.full_path), source_map)
    return _check_file(context, parse_result)


def load_source(source: str) -> tuple[LoadedFile, list[diagnostics.Diagnostic]]:
    """Parse source text without loading from the filesystem, and return it and the diagnostics about it as a whole."""
    parse_result = parser.parse(
        # A lone surrogate becomes invalid UTF-8, as it would be in a file,
        # instead of failing to encode.
        source.encode(errors="surrogatepass"),
        None,
        # Source that is not from the filesystem need not follow the indentation
        # rules.
        check_indentation=False,
    )
    return _check_file(
        file_validation_context.EmptyFileValidationContext(), parse_result
    )


def _check_file(
    context: file_validation_context.FileValidationContext,
    parse_result: parser.ParseResult,
) -> tuple[LoadedFile, list[diagnostics.Diagnostic]]:
    """Check the rules that concern a parsed file as a whole."""
    load_failure = parse_result.load_failure
    if isinstance(
        load_failure,
        syntax_errors.SourceFileReadFailure,
    ):
        return LoadedFile(
            context=context, read_failure=load_failure, definitions={}
        ), parse_result.diagnostics
    if isinstance(load_failure, syntax_errors.DefineSyntaxError):
        return LoadedFile(context=context, read_failure=None, definitions={}), [
            load_failure,
            *parse_result.diagnostics,
        ]

    # The parse produces a program whenever it reports no load failure.
    program = cast("ast.Program", parse_result.program)

    file_diagnostics = parse_result.diagnostics
    definitions: dict[str, ast.GlobalDefinition] = {}
    for definition in program.definitions:
        file_diagnostics.extend(_path_mismatch_diagnostics(definition, context))
        file_diagnostics.extend(_fqun_mismatch_diagnostics(definition, context))
        definition_name = definition.typed_name.full_typed_name
        first_definition = definitions.get(definition_name)
        if first_definition is None:
            definitions[definition_name] = definition
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
        context=context, read_failure=None, definitions=definitions
    ), file_diagnostics


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
    expected_fqun = "" if root_config is None else root_config.fqun.canonical
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
