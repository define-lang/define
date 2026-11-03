"""Pure per-file and per-definition validation for the Define language.

FileStructuralValidator is a stateless worker that loads one file at a time,
and a LoadedFile validates one of its definitions at a time. Neither has access
to shared mutable state.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import msgspec

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics, exceptions, source_map
from define.compiler.parsing import parser
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    definition_validator,
    file_validation_context,
)

if TYPE_CHECKING:
    from define.compiler.data_structures import define_path


type FileDefinitions = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]], ast.GlobalDefinition
]


class LoadedFile(msgspec.Struct):
    """A parsed file, whose definitions are validated only when requested."""

    context: file_validation_context.FileValidationContext
    exception: exceptions.DefineError | None
    # The digest of a file that was read from the filesystem, which lets a
    # source map read it again for diagnostics without keeping its text.
    source_digest: bytes | None
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
            exception=self.exception,
            source_digest=self.source_digest,
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
    """Stateless per-file loader.

    Processes one file: reads from disk, parses, and checks the rules that
    concern the file as a whole. Its definitions are validated separately,
    only when something requests them.
    """

    def load_file(
        self, context: file_validation_context.FileValidationContext
    ) -> LoadedFile:
        """Load and parse a single file."""
        source, digest, load_error = self._load_file(context.full_path)
        if load_error is not None:
            return LoadedFile(
                context=context,
                exception=load_error,
                source_digest=digest,
                file_diagnostics=[],
                definitions=typed_name_dict.TypedNameDict(),
            )
        return self._load_source(
            context=context,
            source=source,
            source_digest=digest,
        )

    def load_source(self, source: str) -> LoadedFile:
        """Parse source text without loading from the filesystem."""
        context = file_validation_context.EmptyFileValidationContext()
        return self._load_source(
            context=context,
            # A lone surrogate becomes invalid UTF-8, as it would be in a file,
            # instead of failing to encode.
            source=source.encode(errors="surrogatepass"),
            source_digest=None,
        )

    @staticmethod
    def _load_source(
        context: file_validation_context.FileValidationContext,
        source: bytes,
        source_digest: bytes | None,
    ) -> LoadedFile:
        """Parse UTF-8 source text and check the rules that concern the whole file."""
        parser_file_path = (
            context.full_path.as_posix_path() if context.is_filesystem_context else None
        )
        parse_result = parser.parse(
            source,
            parser_file_path,
            # Source that is not from the filesystem need not follow the indentation
            # rules.
            check_indentation=context.is_filesystem_context,
        )

        if parse_result.exception is not None:
            return LoadedFile(
                context=context,
                exception=parse_result.exception,
                source_digest=source_digest,
                file_diagnostics=parse_result.diagnostics,
                definitions=typed_name_dict.TypedNameDict(),
            )

        if parse_result.program is None:
            raise ValueError("parse produced no program despite reporting no exception")
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
            exception=None,
            source_digest=source_digest,
            file_diagnostics=file_diagnostics,
            definitions=definitions,
        )

    @staticmethod
    def _load_file(
        path: define_path.DefinePath,
    ) -> tuple[bytes, bytes | None, exceptions.DefineError | None]:
        """Load a Define source file and return its source, digest, and loading error."""
        posix_path = path.as_posix_path()
        try:
            source = pathlib.Path(posix_path).read_bytes()
        except FileNotFoundError:
            return (
                b"",
                None,
                exceptions.SourceFileNotFoundError(
                    filesystem_path=pathlib.Path(posix_path)
                ),
            )
        return source, source_map.source_digest(source), None


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
