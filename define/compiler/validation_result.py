"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from lark import exceptions as lark_exceptions

from define.compiler import (
    ast,
    diagnostics,
    exceptions,
    parser_exceptions,
    stats,
)

if typing.TYPE_CHECKING:
    import pathlib

type AnyValidationException = exceptions.DefineError | lark_exceptions.UnexpectedInput
SYNTAX_ERROR_TYPES = (
    parser_exceptions.DefineSyntaxError,
    lark_exceptions.UnexpectedInput,
)


@dataclass(frozen=True)
class DiscoveredFile:
    """A file discovered during validation that should be validated next."""

    path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    position: ast.SourcePosition


@dataclass(frozen=True)
class ReferenceEdge:
    """A reference from one definition to a global name in another file."""

    enclosing_definition: ast.QualityDefinition
    global_name_reference: ast.TypedGlobalNameReference


@dataclass
class ValidationResult:
    """Validation output for one source file."""

    diagnostics: list[diagnostics.Diagnostic]
    exception: AnyValidationException | None
    source: str | None
    file_path: pathlib.PurePosixPath  # Full path: root_prefix / relative file path.
    root_prefix: pathlib.PurePosixPath
    stats: stats.ValidationTimingStats
    definitions: list[ast.QualityDefinition] = field(default_factory=list)
    reference_edges: list[ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
