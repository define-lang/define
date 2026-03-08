"""Name format validation for the Define language."""

from __future__ import annotations

import string
from pathlib import Path

from define.compiler import ast, diagnostics

_RESERVED_WORDS_DIR = Path(__file__).parent.parent.parent / "reserved_words"


def _load_reserved_words(filename: str) -> frozenset[str]:  # pragma: no mutate
    """Load reserved words from a reserved words file."""
    path = _RESERVED_WORDS_DIR / filename
    words: set[str] = set()
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped:
            words.add(stripped.lower())
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

_LOWERCASE_ALNUM = frozenset(string.ascii_lowercase + string.digits)

_MULTIVERSE_BOUNDARY_CHARS = _LOWERCASE_ALNUM
_MULTIVERSE_CONTINUE_CHARS = _MULTIVERSE_BOUNDARY_CHARS | frozenset("_")

_AUTHORITY_DOMAIN_BOUNDARY_CHARS = _LOWERCASE_ALNUM
_AUTHORITY_DOMAIN_CONTINUE_CHARS = _AUTHORITY_DOMAIN_BOUNDARY_CHARS | frozenset(".-")

# TODO: Add a config option to allow uppercase characters in universe names.
_UNIVERSE_BOUNDARY_CHARS = _LOWERCASE_ALNUM
_UNIVERSE_CONTINUE_CHARS = _UNIVERSE_BOUNDARY_CHARS | frozenset("_")

_PATH_SEGMENT_START_CHARS = frozenset(string.ascii_lowercase + "_")
_PATH_SEGMENT_CONTINUE_CHARS = _PATH_SEGMENT_START_CHARS | frozenset(string.digits)

_LOCAL_NAME_START_CHARS = _PATH_SEGMENT_START_CHARS
_LOCAL_NAME_CONTINUE_CHARS = _PATH_SEGMENT_CONTINUE_CHARS

_AUTHORITY_PATH_START_CHARS = _LOWERCASE_ALNUM | frozenset("_-~")
_AUTHORITY_PATH_CONTINUE_CHARS = _AUTHORITY_PATH_START_CHARS | frozenset(".")


# ---------------------------------------------------------------------------
# Multiverse validation
# ---------------------------------------------------------------------------


def validate_multiverse_name_format(
    multiverse: ast.Multiverse,
) -> list[diagnostics.Diagnostic]:
    """Validate multiverse name character format."""
    name = multiverse.name
    result: list[diagnostics.Diagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.MultiverseNameTooShortDiagnostic(
                position=multiverse.position,
                multiverse_name=name,
            )
        )
    for i, char in enumerate(name):
        if i == 0 or i == len(name) - 1:
            allowed = _MULTIVERSE_BOUNDARY_CHARS
        else:
            allowed = _MULTIVERSE_CONTINUE_CHARS
        if char not in allowed:
            pos = ast.SourcePosition(
                line=multiverse.position.line,
                column=multiverse.position.column + i,
                end_line=multiverse.position.end_line,
                end_column=multiverse.position.end_column,
            )
            result.append(
                diagnostics.MultiverseNameInvalidCharDiagnostic(
                    position=pos,
                    multiverse_name=name,
                    char=char,
                )
            )
            return result
    return result


def validate_multiverse_name_reserved(
    multiverse: ast.Multiverse,
) -> list[diagnostics.ReservedMultiverseNameDiagnostic]:
    """Validate a multiverse name against reserved names."""
    if multiverse.name.lower() in _RESERVED_MULTIVERSE_NAMES:
        return [
            diagnostics.ReservedMultiverseNameDiagnostic(
                position=multiverse.position,
                reserved_name=multiverse.name,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Authority validation
# ---------------------------------------------------------------------------


def _split_authority_name(authority_name: str) -> tuple[str, str | None]:
    slash_index = authority_name.find("/")
    if slash_index < 0:
        return authority_name, None
    return authority_name[:slash_index], authority_name[slash_index + 1 :]


def _validate_authority_domain_format(
    authority: ast.Authority,
    domain: str,
) -> list[diagnostics.Diagnostic]:
    result: list[diagnostics.Diagnostic] = []
    if len(domain) < 2:
        result.append(
            diagnostics.AuthorityDomainTooShortDiagnostic(
                position=authority.position,
                domain=domain,
            )
        )
    for i, char in enumerate(domain):
        if i == 0 or i == len(domain) - 1:
            allowed = _AUTHORITY_DOMAIN_BOUNDARY_CHARS
        else:
            allowed = _AUTHORITY_DOMAIN_CONTINUE_CHARS
        if char not in allowed:
            pos = ast.SourcePosition(
                line=authority.position.line,
                column=authority.position.column + i,
                end_line=authority.position.end_line,
                end_column=authority.position.end_column,
            )
            result.append(
                diagnostics.AuthorityDomainInvalidCharDiagnostic(
                    position=pos,
                    domain=domain,
                    char=char,
                )
            )
            # TODO: We should probably just return a diagnostic for every invalid character.
            return result
    return result


def _validate_authority_path_format(
    authority: ast.Authority,
    domain: str,
    path: str,
) -> list[diagnostics.Diagnostic]:
    result: list[diagnostics.Diagnostic] = []

    col = authority.position.column + len(domain)
    line = authority.position.line
    for segment in path.split("/"):
        col += 1  # skip '/' separator in source text
        diagnostic = _validate_authority_path_segment(
            authority.name, line, col, segment
        )
        if diagnostic is not None:
            result.append(diagnostic)
        col += len(segment)
    return result


def _validate_authority_path_segment(
    authority_name: str, line: int, column: int, segment: str
) -> diagnostics.Diagnostic | None:
    if segment == "":
        return diagnostics.AuthorityPathEmptySegmentDiagnostic(
            position=ast.SourcePosition(
                line=line,
                column=column - 1,
                end_line=line,
                end_column=column,
            ),
            authority=authority_name,
        )
    for i, char in enumerate(segment):
        allowed = (
            _AUTHORITY_PATH_START_CHARS if i == 0 else _AUTHORITY_PATH_CONTINUE_CHARS
        )
        if char not in allowed:
            return diagnostics.InvalidAuthorityPathSegmentDiagnostic(
                position=ast.SourcePosition(
                    line=line,
                    column=column + i,
                    end_line=line,
                    end_column=column + len(segment),
                ),
                segment=segment,
                char=char,
            )
    return None


# TODO: Combine this into a single validate_authority.
def validate_authority_reserved(
    authority: ast.Authority, multiverse: ast.Multiverse | None
) -> list[diagnostics.ReservedNameDiagnostic]:
    """Validate an authority name against reserved names."""
    domain, _ = _split_authority_name(authority.name)
    lowered_domain = domain.lower()

    if lowered_domain in _RESERVED_AUTHORITY_DOMAINS:
        return [
            diagnostics.ReservedAuthorityDomainDiagnostic(
                position=authority.position,
                reserved_name=domain,
            )
        ]

    effective_multiverse = multiverse.name if multiverse else "local"
    if effective_multiverse in ("mv", "local") and "." not in lowered_domain:
        return [
            diagnostics.DotlessAuthorityDomainDiagnostic(
                position=authority.position,
                reserved_name=domain,
                multiverse_name=effective_multiverse,
            )
        ]

    return []


def validate_authority_format(
    authority: ast.Authority,
) -> list[diagnostics.Diagnostic]:
    """Validate authority domain and path character/shape format."""
    domain, path = _split_authority_name(authority.name)
    result: list[diagnostics.Diagnostic] = []
    result.extend(_validate_authority_domain_format(authority, domain))
    if path is not None:
        result.extend(_validate_authority_path_format(authority, domain, path))
    return result


# ---------------------------------------------------------------------------
# Universe validation
# ---------------------------------------------------------------------------


def validate_universe_name_format(
    universe: ast.Universe,
) -> list[diagnostics.Diagnostic]:
    """Validate universe name character format."""
    name = universe.name
    result: list[diagnostics.Diagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.UniverseNameTooShortDiagnostic(
                position=universe.position,
                universe_name=name,
            )
        )
    for i, char in enumerate(name):
        if i == 0 or i == len(name) - 1:
            allowed = _UNIVERSE_BOUNDARY_CHARS
        else:
            allowed = _UNIVERSE_CONTINUE_CHARS
        if char not in allowed:
            pos = ast.SourcePosition(
                line=universe.position.line,
                column=universe.position.column + i,
                end_line=universe.position.end_line,
                end_column=universe.position.end_column,
            )
            result.append(
                diagnostics.UniverseNameInvalidCharDiagnostic(
                    position=pos,
                    universe_name=name,
                    char=char,
                )
            )
            return result
    return result


def validate_universe_name_reserved(
    universe: ast.Universe,
) -> list[diagnostics.ReservedUniverseNameDiagnostic]:
    """Validate a universe name against reserved names."""
    if universe.name.lower() in _RESERVED_UNIVERSE_NAMES:
        return [
            diagnostics.ReservedUniverseNameDiagnostic(
                position=universe.position,
                reserved_name=universe.name,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# FQUN validation
# ---------------------------------------------------------------------------


def validate_fqun(fqun: ast.Fqun) -> list[diagnostics.Diagnostic]:
    """Validate a fully-qualified universe name."""
    result: list[diagnostics.Diagnostic] = []
    if fqun.multiverse is not None:
        result.extend(validate_multiverse_name_format(fqun.multiverse))
        result.extend(validate_multiverse_name_reserved(fqun.multiverse))

    if fqun.authority is None:
        if fqun.universe.name.lower() != "standard":
            result.append(
                diagnostics.UniverseWithoutAuthorityDiagnostic(
                    position=fqun.universe.position,
                    universe_name=fqun.universe.name,
                )
            )
    else:
        result.extend(validate_authority_format(fqun.authority))
        result.extend(validate_authority_reserved(fqun.authority, fqun.multiverse))

    result.extend(validate_universe_name_format(fqun.universe))
    result.extend(validate_universe_name_reserved(fqun.universe))
    return result


# ---------------------------------------------------------------------------
# Global name validation
# ---------------------------------------------------------------------------


def validate_global_name(
    name: ast.GlobalNameContent, must_use_short_form: ast.Fqun | None = None
) -> list[diagnostics.Diagnostic]:
    """Validate a global name and its FQUN."""
    result: list[diagnostics.Diagnostic] = []
    if name.fqun is not None:
        result.extend(validate_fqun(name.fqun))
        if (
            must_use_short_form is not None
            and name.fqun.canonical == must_use_short_form.canonical
        ):
            result.append(
                diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
                    position=name.fqun.position,
                    fqun=must_use_short_form.canonical,
                )
            )
    result.extend(validate_global_name_path(name.path))
    return result


# ---------------------------------------------------------------------------
# Global name path validation
# ---------------------------------------------------------------------------


# TODO: Allow escaped / in paths.
def validate_global_name_path(path: ast.GlobalPathName) -> list[diagnostics.Diagnostic]:
    """Validate path segments in a global name."""
    result: list[diagnostics.Diagnostic] = []
    path_name = path.name
    if not path_name.startswith("/"):
        result.append(
            diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic(
                position=path.position,
                path=path_name,
            )
        )
    if path_name.endswith("/"):
        result.append(
            diagnostics.GlobalNamePathTrailingSlashDiagnostic(
                position=ast.SourcePosition(
                    line=path.position.line,
                    column=path.position.column + len(path_name) - 1,
                    end_line=path.position.end_line,
                    end_column=path.position.end_column,
                ),
                path=path_name,
            )
        )

    segment_start = 1
    while segment_start < len(path_name):
        slash_index = path_name.find("/", segment_start)
        segment_end = slash_index if slash_index >= 0 else len(path_name)
        segment = path_name[segment_start:segment_end]
        if segment == "":
            result.append(
                diagnostics.GlobalNamePathEmptySegmentDiagnostic(
                    position=ast.SourcePosition(
                        line=path.position.line,
                        column=path.position.column + segment_start - 1,
                        end_line=path.position.end_line,
                        end_column=path.position.end_column,
                    ),
                    path=path_name,
                )
            )
        for i, char in enumerate(segment):
            allowed = (
                _PATH_SEGMENT_START_CHARS if i == 0 else _PATH_SEGMENT_CONTINUE_CHARS
            )
            if char not in allowed:
                result.append(
                    diagnostics.InvalidGlobalNamePathCharacterDiagnostic(
                        position=ast.SourcePosition(
                            line=path.position.line,
                            column=path.position.column + segment_start + i,
                            end_line=path.position.end_line,
                            end_column=path.position.end_column,
                        ),
                        segment=segment,
                        char=char,
                    )
                )
                # TODO: Report every invalid character.
                break
        if slash_index < 0:
            break
        segment_start = slash_index + 1
    return result


# ---------------------------------------------------------------------------
# Local name validation
# ---------------------------------------------------------------------------


def validate_local_name_format(
    local_name: ast.LocalNameContent,
) -> list[diagnostics.InvalidLocalNameFormatDiagnostic]:
    """Validate local name character format."""
    name = local_name.name
    for i, char in enumerate(name):
        allowed = _LOCAL_NAME_START_CHARS if i == 0 else _LOCAL_NAME_CONTINUE_CHARS
        if char not in allowed:
            pos = ast.SourcePosition(
                line=local_name.position.line,
                column=local_name.position.column + i,
                end_line=local_name.position.end_line,
                end_column=local_name.position.end_column,
            )
            return [
                diagnostics.InvalidLocalNameFormatDiagnostic(
                    position=pos,
                    local_name=name,
                    char=char,
                )
            ]
    return []


# ---------------------------------------------------------------------------
# Typed name validation
# ---------------------------------------------------------------------------


def validate_typed_name(
    typed_name: ast.TypedNameReference,
    enclosing_definition: ast.QualityDefinition,
) -> list[diagnostics.Diagnostic]:
    """Validate any typed name reference (global or local)."""
    enclosing_fqun = enclosing_definition.typed_name.name_content.fqun
    if isinstance(typed_name, ast.GlobalTypedNameReference):
        return validate_global_name(
            typed_name.name_content, must_use_short_form=enclosing_fqun
        )
    result: list[diagnostics.Diagnostic] = list(
        validate_local_name_format(typed_name.name_content)
    )
    return result
