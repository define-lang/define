"""Semantic validation for the Define language AST."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from compiler import ast  # noqa: TC001

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

    def validate(self) -> list[Diagnostic]:
        """Validate all semantic rules and return collected diagnostics."""
        self._diagnostics = []
        for definition in self._program.definitions:
            self._validate_definition(definition)
        return self._diagnostics

    def _validate_definition(self, definition: ast.QualityDefinition) -> None:
        """Validate a quality definition."""
        self._validate_global_name(definition.name)

    def _validate_global_name(self, name: ast.GlobalName) -> None:
        """Validate a global name and its FQUN."""
        self._validate_fqun(name.fqun)

    def _validate_fqun(self, fqun: ast.Fqun) -> None:
        """Validate a fully-qualified universe name."""
        if fqun.multiverse is not None:
            self._validate_multiverse_name(fqun.multiverse, fqun.position)

        if fqun.authority is not None:
            self._validate_authority(fqun.authority, fqun.multiverse)

        self._validate_universe_name(fqun.universe, fqun.position)

    def _validate_multiverse_name(
        self, name: str, position: ast.SourcePosition
    ) -> None:
        """Validate a multiverse name against reserved names."""
        if name.lower() in _RESERVED_MULTIVERSE_NAMES:
            self._diagnostics.append(
                ReservedMultiverseNameDiagnostic(
                    position=position,
                    message=f"'{name}' is a reserved multiverse name",
                    reserved_name=name,
                )
            )

    def _validate_authority(
        self, authority: ast.Authority, multiverse: str | None
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

        effective_multiverse = multiverse if multiverse else "local"
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

    def _validate_universe_name(self, name: str, position: ast.SourcePosition) -> None:
        """Validate a universe name against reserved names."""
        if name.lower() in _RESERVED_UNIVERSE_NAMES:
            self._diagnostics.append(
                ReservedUniverseNameDiagnostic(
                    position=position,
                    message=f"'{name}' is a reserved universe name",
                    reserved_name=name,
                )
            )
