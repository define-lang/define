"""Parse name content strings into AST name nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from define.compiler import ast, parser_exceptions

if TYPE_CHECKING:
    import lark


def parse_local_name(token: lark.Token) -> ast.LocalName:
    """Parse local name content into an AST local-name node."""
    return ast.LocalName(
        name=token,
        position=ast.SourcePosition.from_token(token),
    )


def parse_global_name_definition(token: lark.Token) -> ast.GlobalNameDefinition:
    """Parse definition-site global name content into an AST node."""
    parsed = _parse_global_name(token)
    if parsed.fqun is None:
        raise parser_exceptions.GlobalNameDefinitionRequiresFqunError(
            token,
            _line(token),
            _column(token),
            token,
        )
    return ast.GlobalNameDefinition(
        position=ast.SourcePosition.from_token(token),
        fqun=parsed.fqun,
        path=parsed.path,
    )


def parse_global_name_reference(token: lark.Token) -> ast.GlobalNameReference:
    """Parse reference-site global name content into an AST node."""
    parsed = _parse_global_name(token)
    return ast.GlobalNameReference(
        position=ast.SourcePosition.from_token(token),
        fqun=parsed.fqun,
        path=parsed.path,
    )


@dataclass(frozen=True)
class _ParsedGlobalName:
    fqun: ast.Fqun | None
    path: ast.GlobalPathName


def _parse_global_name(token: lark.Token) -> _ParsedGlobalName:
    # TODO: Support escaped :
    fqun_sep_index = token.find(":/")
    fqun = None
    path_start = 0
    if fqun_sep_index > 0:
        fqun_text = token[:fqun_sep_index]
        path_text = token[fqun_sep_index + 1 :]
        path_start = fqun_sep_index + 1
        fqun = _parse_fqun(token, fqun_text)
    else:
        path_text = token

    global_path = _parse_global_path(token, path_text, path_start)
    return _ParsedGlobalName(fqun, global_path)


def _parse_fqun(token: lark.Token, text: str) -> ast.Fqun:
    # TODO: Support escaped :
    parts = text.split(":")
    if len(parts) not in {1, 2, 3} or any(part == "" for part in parts):
        raise parser_exceptions.GlobalNameInvalidFqunFormatError(
            token,
            _line(token),
            _column(token),
            token,
        )

    multiverse = None
    authority = None
    fqun_position = _position_for_offsets(token, 0, len(text))
    if len(parts) == 1:
        universe = ast.Universe(
            name=parts[0],
            position=fqun_position,
        )
    elif len(parts) == 2:
        authority_text, universe_text = parts
        authority_start = 0
        authority_end = len(authority_text)
        universe_start = authority_end + 1
        universe_end = universe_start + len(universe_text)
        authority = _parse_authority(
            token,
            authority_text,
            authority_start,
        )
        universe = ast.Universe(
            name=universe_text,
            position=_position_for_offsets(token, universe_start, universe_end),
        )
    else:
        multiverse_text, authority_text, universe_text = parts
        multiverse_start = 0
        multiverse_end = len(multiverse_text)
        authority_start = multiverse_end + 1
        authority_end = authority_start + len(authority_text)
        universe_start = authority_end + 1
        universe_end = universe_start + len(universe_text)
        multiverse = ast.Multiverse(
            name=multiverse_text,
            position=_position_for_offsets(token, multiverse_start, multiverse_end),
        )
        authority = _parse_authority(
            token,
            authority_text,
            authority_start,
        )
        universe = ast.Universe(
            name=universe_text,
            position=_position_for_offsets(token, universe_start, universe_end),
        )

    return ast.Fqun(
        multiverse=multiverse,
        authority=authority,
        universe=universe,
        position=fqun_position,
    )


def _parse_authority(
    token: lark.Token,
    text: str,
    absolute_start: int,
) -> ast.Authority:
    # TODO: We can defer all of this to validation, because segmentation is only needed for validation.
    pieces = text.split("/")
    if any(piece == "" for piece in pieces):
        raise parser_exceptions.GlobalNameEmptyAuthorityPathSegmentError(
            token,
            _line(token),
            _column(token),
            token,
        )
    domain = pieces[0]
    path = pieces[1:]
    return ast.Authority(
        domain=domain,
        path=path,
        position=_position_for_offsets(
            token, absolute_start, absolute_start + len(text)
        ),
    )


def _parse_global_path(
    token: lark.Token,
    text: str,
    start_column: int,
) -> ast.GlobalPathName:
    base_column = _column(token)
    start_offset = start_column
    # TODO: We can defer all of this to validation, because segmentation is only needed for validation.
    if not text.startswith("/"):
        raise parser_exceptions.GlobalNamePathMustStartWithSlashError(
            token,
            _line(token),
            base_column + start_offset,
            token,
        )
    if text.endswith("/"):
        raise parser_exceptions.GlobalNamePathTrailingSlashError(
            token,
            _line(token),
            base_column + start_offset + len(text) - 1,
            token,
        )

    segments: list[ast.GlobalPathNameSegment] = []
    segment_start = 1
    while segment_start < len(text):
        slash_index = text.find("/", segment_start)
        segment_end = slash_index if slash_index >= 0 else len(text)
        segment = text[segment_start:segment_end]
        if segment == "":
            raise parser_exceptions.GlobalNamePathEmptySegmentError(
                token,
                _line(token),
                base_column + start_offset + segment_start,
                token,
            )
        offset = start_offset + segment_start
        segments.append(
            ast.GlobalPathNameSegment(
                name=segment,
                position=_position_for_offsets(token, offset, offset + len(segment)),
            )
        )
        if slash_index < 0:
            break
        segment_start = slash_index + 1
    return ast.GlobalPathName(
        segments=segments,
        position=_position_for_offsets(token, start_offset, start_offset + len(text)),
    )


def _line(token: lark.Token) -> int:
    line = token.line
    if line is None:
        raise ValueError("Expected token.line to be present")
    return line


def _column(token: lark.Token) -> int:
    column = token.column
    if column is None:
        raise ValueError("Expected token.column to be present")
    return column


def _position_for_offsets(
    token: lark.Token, start_offset: int, end_offset: int
) -> ast.SourcePosition:
    line = _line(token)
    base_column = _column(token)
    return ast.SourcePosition(
        line=line,
        column=base_column + start_offset,
        end_line=line,
        end_column=base_column + end_offset,
    )
