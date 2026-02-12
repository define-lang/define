"""Name format validation for the Define language."""

from __future__ import annotations

import string

from define.compiler import ast, diagnostics

_LOWERCASE_ALNUM = frozenset(string.ascii_lowercase + string.digits)

_MULTIVERSE_BOUNDARY_CHARS = _LOWERCASE_ALNUM
_MULTIVERSE_CONTINUE_CHARS = _MULTIVERSE_BOUNDARY_CHARS | frozenset("_")

_AUTHORITY_DOMAIN_BOUNDARY_CHARS = _LOWERCASE_ALNUM
_AUTHORITY_DOMAIN_CONTINUE_CHARS = _AUTHORITY_DOMAIN_BOUNDARY_CHARS | frozenset(".-")

_UNIVERSE_BOUNDARY_CHARS = frozenset(string.ascii_letters + string.digits)
_UNIVERSE_CONTINUE_CHARS = _UNIVERSE_BOUNDARY_CHARS | frozenset("_")

_PATH_SEGMENT_START_CHARS = frozenset(string.ascii_lowercase + "_")
_PATH_SEGMENT_CONTINUE_CHARS = _PATH_SEGMENT_START_CHARS | frozenset(string.digits)

_LOCAL_NAME_START_CHARS = _PATH_SEGMENT_START_CHARS
_LOCAL_NAME_CONTINUE_CHARS = _PATH_SEGMENT_CONTINUE_CHARS

_AUTHORITY_PATH_START_CHARS = _LOWERCASE_ALNUM | frozenset("_-~")
_AUTHORITY_PATH_CONTINUE_CHARS = _AUTHORITY_PATH_START_CHARS | frozenset(".")


def validate_multiverse_name_format(
    multiverse: ast.Multiverse,
) -> list[diagnostics.InvalidMultiverseNameDiagnostic]:
    """Validate multiverse name character format."""
    name = multiverse.name
    result: list[diagnostics.InvalidMultiverseNameDiagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.InvalidMultiverseNameDiagnostic(
                position=multiverse.position,
                message=f"multiverse name '{name}' must be at least 2 characters",
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
                diagnostics.InvalidMultiverseNameDiagnostic(
                    position=pos,
                    message=f"invalid character '{char}' in multiverse name '{name}'",
                    multiverse_name=name,
                )
            )
            return result
    return result


def validate_authority_domain_format(
    authority: ast.Authority,
) -> list[diagnostics.InvalidAuthorityDomainDiagnostic]:
    """Validate authority domain character format."""
    domain = authority.domain
    result: list[diagnostics.InvalidAuthorityDomainDiagnostic] = []
    if len(domain) < 2:
        result.append(
            diagnostics.InvalidAuthorityDomainDiagnostic(
                position=authority.position,
                message=f"authority domain '{domain}' must be at least 2 characters",
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
                diagnostics.InvalidAuthorityDomainDiagnostic(
                    position=pos,
                    message=f"invalid character '{char}' in authority domain '{domain}'",
                    domain=domain,
                )
            )
            return result
    return result


def validate_authority_path_format(
    authority: ast.Authority,
) -> list[diagnostics.InvalidAuthorityPathSegmentDiagnostic]:
    """Validate authority path segment character format."""
    result: list[diagnostics.InvalidAuthorityPathSegmentDiagnostic] = []
    col = authority.position.column + len(authority.domain)
    line = authority.position.line
    for segment in authority.path:
        col += 1  # skip '/' separator in source text
        for i, char in enumerate(segment):
            allowed = (
                _AUTHORITY_PATH_START_CHARS
                if i == 0
                else _AUTHORITY_PATH_CONTINUE_CHARS
            )
            if char not in allowed:
                pos = ast.SourcePosition(
                    line=line,
                    column=col + i,
                    end_line=line,
                    end_column=col + len(segment),
                )
                result.append(
                    diagnostics.InvalidAuthorityPathSegmentDiagnostic(
                        position=pos,
                        message=(
                            f"invalid character '{char}' "
                            f"in authority path segment '{segment}'"
                        ),
                        segment=segment,
                    )
                )
                break
        col += len(segment)
    return result


def validate_universe_name_format(
    universe: ast.Universe,
) -> list[diagnostics.InvalidUniverseNameFormatDiagnostic]:
    """Validate universe name character format."""
    name = universe.name
    result: list[diagnostics.InvalidUniverseNameFormatDiagnostic] = []
    if len(name) < 2:
        result.append(
            diagnostics.InvalidUniverseNameFormatDiagnostic(
                position=universe.position,
                message=f"universe name '{name}' must be at least 2 characters",
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
                diagnostics.InvalidUniverseNameFormatDiagnostic(
                    position=pos,
                    message=f"invalid character '{char}' in universe name '{name}'",
                    universe_name=name,
                )
            )
            return result
    return result


def validate_global_name_path_segment(
    segment: ast.GlobalPathNameSegment,
) -> diagnostics.InvalidGlobalNamePathDiagnostic | None:
    """Validate a single path segment in a global name."""
    for i, char in enumerate(segment.name):
        allowed = _PATH_SEGMENT_START_CHARS if i == 0 else _PATH_SEGMENT_CONTINUE_CHARS
        if char not in allowed:
            pos = ast.SourcePosition(
                line=segment.position.line,
                column=segment.position.column + i,
                end_line=segment.position.end_line,
                end_column=segment.position.end_column,
            )
            return diagnostics.InvalidGlobalNamePathDiagnostic(
                position=pos,
                message=(
                    f"invalid character '{char}' in path segment '{segment.name}'"
                ),
                segment=segment.name,
            )
    return None


def validate_global_name_path(
    path: ast.GlobalPathName,
) -> list[diagnostics.InvalidGlobalNamePathDiagnostic]:
    """Validate path segments in a global name."""
    result: list[diagnostics.InvalidGlobalNamePathDiagnostic] = []
    for segment in path.segments:
        diagnostic = validate_global_name_path_segment(segment)
        if diagnostic is not None:
            result.append(diagnostic)
    return result


def validate_local_name_format(
    local_def: ast.LocalPositionDefinition,
) -> list[diagnostics.InvalidLocalNameFormatDiagnostic]:
    """Validate local name character format."""
    local_name = local_def.local_name
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
                    message=f"invalid character '{char}' in local name '{name}'",
                    local_name=name,
                )
            ]
    return []
