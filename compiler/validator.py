"""Semantic validation for the Define language AST."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from compiler import ast

_SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"


def _load_reserved_words(filename: str) -> frozenset[str]:
    """Load reserved words from a spec file."""
    path = _SPEC_DIR / filename
    words = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            words.add(line.lower())
    return frozenset(words)


_SMALL_COMMON_WORDS = _load_reserved_words("small_common_words.txt")
_PACKAGE_REPOSITORIES = _load_reserved_words("package_repositories.txt")
_PROGRAMMING_LANGUAGES = _load_reserved_words("programming_languages.txt")

_RESERVED_UNIVERSE_NAMES_EXPLICIT: frozenset[str] = frozenset(
    {
        "standard",
        "example",
        "authority",
        "define",
        "fqun",
        "local",
        "multiverse",
        "mv",
        "name",
        "type",
        "universe",
    }
)

_RESERVED_UNIVERSE_NAMES = _RESERVED_UNIVERSE_NAMES_EXPLICIT | _SMALL_COMMON_WORDS

_RESERVED_AUTHORITY_DOMAINS = _RESERVED_UNIVERSE_NAMES | frozenset({"example.com"})

_RESERVED_MULTIVERSE_NAMES = (
    (_RESERVED_UNIVERSE_NAMES - frozenset({"mv"}))
    | _PACKAGE_REPOSITORIES
    | _PROGRAMMING_LANGUAGES
)


@dataclass
class Diagnostic:
    """Base class for all validation diagnostics."""

    position: ast.SourcePosition
    message: str

    def format(self, source_lines: list[str]) -> str:
        """Format the diagnostic with source context and caret pointer."""
        line_idx = self.position.line - 1
        source_line = (
            source_lines[line_idx] if 0 <= line_idx < len(source_lines) else ""
        )

        column = self.position.column
        caret_line = " " * (column - 1) + "^"

        return (
            f"line {self.position.line}, column {self.position.column}: "
            f"{self.message}\n"
            f"  {source_line}\n"
            f"  {caret_line}"
        )


@dataclass
class ReservedNameDiagnostic(Diagnostic):
    """Base class for reserved name diagnostics."""

    reserved_name: str


@dataclass
class ReservedUniverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved universe name is used."""


@dataclass
class ReservedAuthorityNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority name is used."""


@dataclass
class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""


@dataclass
class PathMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str


@dataclass
class UniverseWithoutAuthorityDiagnostic(Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str


@dataclass
class DuplicateDefinitionDiagnostic(Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int


class Validator:
    """Validates semantic rules for a Define program AST."""

    def __init__(self, program: ast.Program, source: str) -> None:
        """Initialize validator with a program AST and source code."""
        self._program = program
        self._source = source
        self._diagnostics: list[Diagnostic] = []

    @cached_property
    def source_lines(self) -> list[str]:
        """Source code split into lines, for use with Diagnostic.format()."""
        return self._source.splitlines()

    def validate(self, file_path: str | None = None) -> list[Diagnostic]:
        """Validate all semantic rules and return collected diagnostics.

        Args:
            file_path: Optional path to the source file, relative to project root,
                without the .def extension. When provided, the validator operates
                in filesystem context and validates that definition paths match
                the file path. When None, the validator operates in non-filesystem
                context and skips path matching validation.
        """
        self._diagnostics = []
        self._file_path = file_path
        self._seen_definitions: dict[
            tuple[type, tuple[str, ...]], ast.QualityDefinition
        ] = {}
        for definition in self._program.definitions:
            self._validate_definition(definition)
        return self._diagnostics

    def _validate_definition(self, definition: ast.QualityDefinition) -> None:
        """Validate a quality definition."""
        self._validate_global_name(definition.name)
        self._validate_path_matches_file(definition)
        self._validate_not_duplicate(definition)

    def _validate_global_name(self, name: ast.GlobalName) -> None:
        """Validate a global name and its FQUN."""
        self._validate_fqun(name.fqun)

    def _validate_fqun(self, fqun: ast.Fqun) -> None:
        """Validate a fully-qualified universe name."""
        if fqun.multiverse is not None:
            self._validate_multiverse_name(fqun.multiverse)

        if fqun.authority is None:
            if fqun.universe.name.lower() != "standard":
                self._diagnostics.append(
                    UniverseWithoutAuthorityDiagnostic(
                        position=fqun.universe.position,
                        message=(
                            f"universe '{fqun.universe.name}' requires an authority; "
                            f"only 'standard' may be used without an authority"
                        ),
                        universe_name=fqun.universe.name,
                    )
                )
        else:
            self._validate_authority(fqun.authority, fqun.multiverse)

        self._validate_universe_name(fqun.universe)

    def _validate_multiverse_name(self, multiverse: ast.Multiverse) -> None:
        """Validate a multiverse name against reserved names."""
        if multiverse.name.lower() in _RESERVED_MULTIVERSE_NAMES:
            self._diagnostics.append(
                ReservedMultiverseNameDiagnostic(
                    position=multiverse.position,
                    message=f"'{multiverse.name}' is a reserved multiverse name",
                    reserved_name=multiverse.name,
                )
            )

    def _validate_authority(
        self, authority: ast.Authority, multiverse: ast.Multiverse | None
    ) -> None:
        """Validate an authority name."""
        domain = authority.domain.lower()

        if domain in _RESERVED_AUTHORITY_DOMAINS:
            self._diagnostics.append(
                ReservedAuthorityNameDiagnostic(
                    position=authority.position,
                    message=f"'{authority.domain}' is a reserved authority domain",
                    reserved_name=authority.domain,
                )
            )
            return

        effective_multiverse = multiverse.name if multiverse else "local"
        if effective_multiverse in ("mv", "local") and "." not in domain:
            self._diagnostics.append(
                ReservedAuthorityNameDiagnostic(
                    position=authority.position,
                    message=(
                        f"'{authority.domain}' is reserved: "
                        f"authority domains without '.' are reserved "
                        f"in the '{effective_multiverse}' multiverse"
                    ),
                    reserved_name=authority.domain,
                )
            )

    def _validate_universe_name(self, universe: ast.Universe) -> None:
        """Validate a universe name against reserved names."""
        if universe.name.lower() in _RESERVED_UNIVERSE_NAMES:
            self._diagnostics.append(
                ReservedUniverseNameDiagnostic(
                    position=universe.position,
                    message=f"'{universe.name}' is a reserved universe name",
                    reserved_name=universe.name,
                )
            )

    def _validate_path_matches_file(self, definition: ast.QualityDefinition) -> None:
        """Validate that the definition's path matches the file path."""
        if self._file_path is None:
            return

        definition_path = "/" + "/".join(definition.name.path)
        expected_path = "/" + self._file_path

        if definition_path != expected_path:
            self._diagnostics.append(
                PathMismatchDiagnostic(
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
        key = (type(definition), tuple(definition.name.path))
        if key in self._seen_definitions:
            first_def = self._seen_definitions[key]
            match definition:
                case ast.PositionDefinition():
                    def_type = "position"
                case ast.ActionDefinition():
                    def_type = "action"
                case _:
                    raise TypeError(f"Unknown definition type: {type(definition)}")
            path_str = "/" + "/".join(definition.name.path)
            self._diagnostics.append(
                DuplicateDefinitionDiagnostic(
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
