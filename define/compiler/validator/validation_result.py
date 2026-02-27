"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import (
    ast,
    diagnostics,
    exceptions,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib

    from define.compiler.validator import stats

type AnyValidationException = exceptions.DefineError | lark_standalone.UnexpectedInput


@dataclass
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

    @cached_property
    def fully_qualified_typed_name(self) -> str:
        """Return the fully qualified typed-name key for this edge target."""
        if self.global_name_reference.name_content.fqun is None:
            return self.global_name_reference.fully_qualified_typed_name(
                in_universe=self.enclosing_definition.name.fqun
            )
        return self.global_name_reference.fully_qualified_typed_name()


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
