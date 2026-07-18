"""Name format validation for the Define language."""

from __future__ import annotations

import string
from pathlib import Path, PurePosixPath

from define.compiler import ast, constants, diagnostics

_RESERVED_WORDS_DIR = Path(__file__).parent.parent.parent.parent / "reserved_words"


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
        constants.DEFAULT_MULTIVERSE,
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


def _validate_multiverse_name_format(
    multiverse: ast.Multiverse,
) -> list[diagnostics.Diagnostic]:
    """Validate multiverse name character format."""
    name = multiverse.name
    result: list[diagnostics.Diagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.MultiverseNameTooShortDiagnostic(
                location=multiverse.location,
                multiverse_name=name,
            )
        )
    for i, char in enumerate(name):
        if i == 0 or i == len(name) - 1:
            allowed = _MULTIVERSE_BOUNDARY_CHARS
        else:
            allowed = _MULTIVERSE_CONTINUE_CHARS
        if char not in allowed:
            location = ast.SourceLocation(
                line=multiverse.location.line,
                column=multiverse.location.column + i,
                end_line=multiverse.location.end_line,
                end_column=multiverse.location.end_column,
                file_path=multiverse.location.file_path,
            )
            result.append(
                diagnostics.MultiverseNameInvalidCharDiagnostic(
                    location=location,
                    multiverse_name=name,
                    char=char,
                )
            )
            return result
    return result


def _validate_multiverse_name_reserved(
    multiverse: ast.Multiverse,
) -> list[diagnostics.ReservedMultiverseNameDiagnostic]:
    """Validate a multiverse name against reserved names."""
    if multiverse.name.lower() in _RESERVED_MULTIVERSE_NAMES:
        return [
            diagnostics.ReservedMultiverseNameDiagnostic(
                location=multiverse.location,
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
                location=authority.location,
                domain=domain,
            )
        )
    for i, char in enumerate(domain):
        if i == 0 or i == len(domain) - 1:
            allowed = _AUTHORITY_DOMAIN_BOUNDARY_CHARS
        else:
            allowed = _AUTHORITY_DOMAIN_CONTINUE_CHARS
        if char not in allowed:
            location = ast.SourceLocation(
                line=authority.location.line,
                column=authority.location.column + i,
                end_line=authority.location.end_line,
                end_column=authority.location.end_column,
                file_path=authority.location.file_path,
            )
            result.append(
                diagnostics.AuthorityDomainInvalidCharDiagnostic(
                    location=location,
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

    col = authority.location.column + len(domain)
    line = authority.location.line
    file_path = authority.location.file_path
    for segment in path.split("/"):
        col += 1  # skip '/' separator in source text
        diagnostic = _validate_authority_path_segment(
            authority.name, line, col, segment, file_path
        )
        if diagnostic is not None:
            result.append(diagnostic)
        col += len(segment)
    return result


def _validate_authority_path_segment(
    authority_name: str,
    line: int,
    column: int,
    segment: str,
    file_path: PurePosixPath | None = None,
) -> diagnostics.Diagnostic | None:
    if segment == "":
        return diagnostics.AuthorityPathEmptySegmentDiagnostic(
            location=ast.SourceLocation(
                line=line,
                column=column - 1,
                end_line=line,
                end_column=column,
                file_path=file_path,
            ),
            authority=authority_name,
        )
    for i, char in enumerate(segment):
        allowed = (
            _AUTHORITY_PATH_START_CHARS if i == 0 else _AUTHORITY_PATH_CONTINUE_CHARS
        )
        if char not in allowed:
            return diagnostics.InvalidAuthorityPathSegmentDiagnostic(
                location=ast.SourceLocation(
                    line=line,
                    column=column + i,
                    end_line=line,
                    end_column=column + len(segment),
                    file_path=file_path,
                ),
                segment=segment,
                char=char,
            )
    return None


def _validate_authority_reserved(
    authority: ast.Authority, multiverse: ast.Multiverse | None
) -> list[diagnostics.ReservedNameDiagnostic]:
    """Validate an authority name against reserved names."""
    domain, _ = _split_authority_name(authority.name)
    lowered_domain = domain.lower()

    if lowered_domain in _RESERVED_AUTHORITY_DOMAINS:
        return [
            diagnostics.ReservedAuthorityDomainDiagnostic(
                location=authority.location,
                reserved_name=domain,
            )
        ]

    effective_multiverse = (
        multiverse.name if multiverse else constants.DEFAULT_MULTIVERSE
    )
    if (
        effective_multiverse in ("mv", constants.DEFAULT_MULTIVERSE)
        and "." not in lowered_domain
    ):
        return [
            diagnostics.DotlessAuthorityDomainDiagnostic(
                location=authority.location,
                reserved_name=domain,
                multiverse_name=effective_multiverse,
            )
        ]

    return []


def _validate_authority(
    authority: ast.Authority, multiverse: ast.Multiverse | None
) -> list[diagnostics.Diagnostic]:
    """Validate an authority name."""
    domain, path = _split_authority_name(authority.name)
    result: list[diagnostics.Diagnostic] = []
    result.extend(_validate_authority_domain_format(authority, domain))
    if path is not None:
        result.extend(_validate_authority_path_format(authority, domain, path))
    result.extend(_validate_authority_reserved(authority, multiverse))
    return result


# ---------------------------------------------------------------------------
# Universe validation
# ---------------------------------------------------------------------------


def _validate_universe_name_format(
    universe: ast.Universe,
) -> list[diagnostics.Diagnostic]:
    """Validate universe name character format."""
    name = universe.name
    result: list[diagnostics.Diagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.UniverseNameTooShortDiagnostic(
                location=universe.location,
                universe_name=name,
            )
        )
    for i, char in enumerate(name):
        if i == 0 or i == len(name) - 1:
            allowed = _UNIVERSE_BOUNDARY_CHARS
        else:
            allowed = _UNIVERSE_CONTINUE_CHARS
        if char not in allowed:
            location = ast.SourceLocation(
                line=universe.location.line,
                column=universe.location.column + i,
                end_line=universe.location.end_line,
                end_column=universe.location.end_column,
                file_path=universe.location.file_path,
            )
            result.append(
                diagnostics.UniverseNameInvalidCharDiagnostic(
                    location=location,
                    universe_name=name,
                    char=char,
                )
            )
            return result
    return result


def _validate_universe_name_reserved(
    universe: ast.Universe,
) -> list[diagnostics.ReservedUniverseNameDiagnostic]:
    """Validate a universe name against reserved names."""
    if universe.name.lower() in _RESERVED_UNIVERSE_NAMES:
        return [
            diagnostics.ReservedUniverseNameDiagnostic(
                location=universe.location,
                reserved_name=universe.name,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# FQUN validation
# ---------------------------------------------------------------------------


def _validate_fqun(fqun: ast.Fqun) -> list[diagnostics.Diagnostic]:
    """Validate a fully-qualified universe name."""
    result: list[diagnostics.Diagnostic] = []
    if fqun.multiverse is not None:
        result.extend(_validate_multiverse_name_format(fqun.multiverse))
        result.extend(_validate_multiverse_name_reserved(fqun.multiverse))

    if fqun.authority is None:
        if fqun.universe.name.lower() != "standard":
            result.append(
                diagnostics.UniverseWithoutAuthorityDiagnostic(
                    location=fqun.universe.location,
                    universe_name=fqun.universe.name,
                )
            )
    else:
        result.extend(_validate_authority(fqun.authority, fqun.multiverse))

    result.extend(_validate_universe_name_format(fqun.universe))
    result.extend(_validate_universe_name_reserved(fqun.universe))
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
        result.extend(_validate_fqun(name.fqun))
        if (
            must_use_short_form is not None
            and name.fqun.canonical == must_use_short_form.canonical
        ):
            result.append(
                diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
                    location=name.fqun.location,
                    fqun=must_use_short_form.canonical,
                )
            )
    result.extend(_validate_global_name_path(name.path))
    return result


# ---------------------------------------------------------------------------
# Global name path validation
# ---------------------------------------------------------------------------


# TODO: Allow escaped / in paths.
def _validate_global_name_path(
    path: ast.GlobalPathName,
) -> list[diagnostics.Diagnostic]:
    """Validate path segments in a global name."""
    result: list[diagnostics.Diagnostic] = []
    path_name = path.name
    if not path_name.startswith("/"):
        result.append(
            diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic(
                location=path.location,
                path=path_name,
            )
        )
    if path_name.endswith("/"):
        result.append(
            diagnostics.GlobalNamePathTrailingSlashDiagnostic(
                location=ast.SourceLocation(
                    line=path.location.line,
                    column=path.location.column + len(path_name) - 1,
                    end_line=path.location.end_line,
                    end_column=path.location.end_column,
                    file_path=path.location.file_path,
                ),
                path=path_name,
            )
        )

    segment_start = 1
    while segment_start < len(path_name):
        slash_index = path_name.find("/", segment_start)
        segment_end = slash_index if slash_index != -1 else len(path_name)
        segment = path_name[segment_start:segment_end]
        if segment == "":
            result.append(
                diagnostics.GlobalNamePathEmptySegmentDiagnostic(
                    location=ast.SourceLocation(
                        line=path.location.line,
                        column=path.location.column + segment_start - 1,
                        end_line=path.location.end_line,
                        end_column=path.location.end_column,
                        file_path=path.location.file_path,
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
                        location=ast.SourceLocation(
                            line=path.location.line,
                            column=path.location.column + segment_start + i,
                            end_line=path.location.end_line,
                            end_column=path.location.end_column,
                            file_path=path.location.file_path,
                        ),
                        segment=segment,
                        char=char,
                    )
                )
                # TODO: Report every invalid character.
                break
        if slash_index == -1:
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
            location = ast.SourceLocation(
                line=local_name.location.line,
                column=local_name.location.column + i,
                end_line=local_name.location.end_line,
                end_column=local_name.location.end_column,
                file_path=local_name.location.file_path,
            )
            return [
                diagnostics.InvalidLocalNameFormatDiagnostic(
                    location=location,
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
