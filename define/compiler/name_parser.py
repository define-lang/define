"""Parse name content strings into AST name nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from define.compiler import ast, parser_exceptions

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler.lark import lark_standalone


def parse_local_name(
    token: lark_standalone.Token, file_path: PurePosixPath | None = None
) -> ast.LocalNameContent:
    """Parse local name content into an AST local-name node."""
    return ast.LocalNameContent(
        name=token,
        location=ast.SourceLocation.from_token(token, file_path=file_path),
    )


def parse_global_name_definition(
    token: lark_standalone.Token, file_path: PurePosixPath | None = None
) -> ast.DefinitionGlobalNameContent:
    """Parse definition-site global name content into an AST node."""
    parsed = _parse_global_name(token, file_path)
    if parsed.fqun is None:
        raise parser_exceptions.DefinitionGlobalNameContentRequiresFqun(
            token,
            _line(token),
            _column(token),
            None,
        )
    return ast.DefinitionGlobalNameContent(
        location=ast.SourceLocation.from_token(token, file_path=file_path),
        fqun=parsed.fqun,
        path=parsed.path,
    )


def parse_global_name_reference(
    token: lark_standalone.Token, file_path: PurePosixPath | None = None
) -> ast.ReferenceGlobalNameContent:
    """Parse reference-site global name content into an AST node."""
    parsed = _parse_global_name(token, file_path)
    return ast.ReferenceGlobalNameContent(
        location=ast.SourceLocation.from_token(token, file_path=file_path),
        fqun=parsed.fqun,
        path=parsed.path,
    )


@dataclass(frozen=True)
class _ParsedGlobalName:
    fqun: ast.Fqun | None
    path: ast.GlobalPathName


def _parse_global_name(
    token: lark_standalone.Token, file_path: PurePosixPath | None = None
) -> _ParsedGlobalName:
    # TODO: Support escaped :
    fqun_sep_index = token.rfind(":")
    fqun = None
    path_start = 0
    if fqun_sep_index > 0:
        fqun_text = token[:fqun_sep_index]
        path_text = token[fqun_sep_index + 1 :]
        path_start = fqun_sep_index + 1
        fqun = _parse_fqun(token, fqun_text, file_path)
    else:
        path_text = token

    global_path = ast.GlobalPathName(
        name=path_text,
        location=_position_for_offsets(
            token, path_start, path_start + len(path_text), file_path
        ),
    )
    return _ParsedGlobalName(fqun, global_path)


def _parse_fqun(
    token: lark_standalone.Token, text: str, file_path: PurePosixPath | None = None
) -> ast.Fqun:
    # TODO: Support escaped :
    parts = text.split(":")
    if len(parts) not in {1, 2, 3}:
        raise parser_exceptions.GlobalNameInvalidFqunFormat(
            token,
            _line(token),
            _column(token),
            None,
        )

    multiverse = None
    authority = None
    fqun_position = _position_for_offsets(token, 0, len(text), file_path)
    if len(parts) == 1:
        universe = ast.Universe(
            name=parts[0],
            location=fqun_position,
        )
    elif len(parts) == 2:
        authority_text, universe_text = parts
        authority_start = 0
        authority_end = len(authority_text)
        universe_start = authority_end + 1
        universe_end = universe_start + len(universe_text)
        authority = ast.Authority(
            name=authority_text,
            location=_position_for_offsets(
                token, authority_start, authority_start + len(authority_text), file_path
            ),
        )
        universe = ast.Universe(
            name=universe_text,
            location=_position_for_offsets(
                token, universe_start, universe_end, file_path
            ),
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
            location=_position_for_offsets(
                token, multiverse_start, multiverse_end, file_path
            ),
        )
        authority = ast.Authority(
            name=authority_text,
            location=_position_for_offsets(
                token, authority_start, authority_start + len(authority_text), file_path
            ),
        )
        universe = ast.Universe(
            name=universe_text,
            location=_position_for_offsets(
                token, universe_start, universe_end, file_path
            ),
        )

    return ast.Fqun(
        multiverse=multiverse,
        authority=authority,
        universe=universe,
        location=fqun_position,
    )


def _line(token: lark_standalone.Token) -> int:
    line = token.line
    if line is None:
        raise ValueError("Expected token.line to be present")
    return line


def _column(token: lark_standalone.Token) -> int:
    column = token.column
    if column is None:
        raise ValueError("Expected token.column to be present")
    return column


def _position_for_offsets(
    token: lark_standalone.Token,
    start_offset: int,
    end_offset: int,
    file_path: PurePosixPath | None = None,
) -> ast.SourceLocation:
    line = _line(token)
    base_column = _column(token)
    return ast.SourceLocation(
        line=line,
        column=base_column + start_offset,
        end_line=line,
        end_column=base_column + end_offset,
        file_path=file_path,
    )
