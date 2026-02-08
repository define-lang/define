"""Lark transformer to convert parse tree to AST nodes."""

from typing import cast

import lark
from lark.visitors import Discard, v_args

from define.compiler import ast


class DefineTransformer(lark.Transformer[lark.Token, ast.Program]):
    """Transforms the parse tree from Parser into AST nodes."""

    @v_args(meta=True)
    def start(
        self, meta: lark.tree.Meta, items: list[ast.QualityDefinition]
    ) -> ast.Program:
        """Transform the root rule into a Program."""
        return ast.Program(
            definitions=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def position_definition(
        self, meta: lark.tree.Meta, items: list[ast.GlobalName]
    ) -> ast.PositionDefinition:
        """Transform a position definition."""
        return ast.PositionDefinition(
            name=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def action_definition(
        self, meta: lark.tree.Meta, items: list[ast.GlobalName]
    ) -> ast.ActionDefinition:
        """Transform an action definition."""
        return ast.ActionDefinition(
            name=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    def definition(self, items: list[ast.QualityDefinition]) -> ast.QualityDefinition:
        """Unwrap the definition wrapper rule."""
        return items[0]

    @v_args(meta=True)
    def global_name(
        self, meta: lark.tree.Meta, items: list[ast.Fqun | list[str]]
    ) -> ast.GlobalName:
        """Transform a global name with FQUN and path."""
        fqun = cast("ast.Fqun", items[0])
        path = cast("list[str]", items[1])
        return ast.GlobalName(
            fqun=fqun,
            path=path,
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def fqun(
        self,
        meta: lark.tree.Meta,
        items: list[ast.Multiverse | ast.Authority | ast.Universe],
    ) -> ast.Fqun:
        """Transform a fully-qualified universe name."""
        position = ast.SourcePosition.from_meta(meta)
        match len(items):
            case 3:
                return ast.Fqun(
                    multiverse=cast("ast.Multiverse", items[0]),
                    authority=cast("ast.Authority", items[1]),
                    universe=cast("ast.Universe", items[2]),
                    position=position,
                )
            case 2:
                return ast.Fqun(
                    multiverse=None,
                    authority=cast("ast.Authority", items[0]),
                    universe=cast("ast.Universe", items[1]),
                    position=position,
                )
            case 1:
                return ast.Fqun(
                    multiverse=None,
                    authority=None,
                    universe=cast("ast.Universe", items[0]),
                    position=position,
                )
            case _:
                raise ValueError(f"Unexpected fqun items: {items}")

    def MULTIVERSE_NAME(self, token: lark.Token) -> ast.Multiverse:  # noqa: N802
        """Transform a multiverse name token into an AST node."""
        return ast.Multiverse(
            name=str(token),
            position=ast.SourcePosition.from_token(token),
        )

    def UNIVERSE_NAME(self, token: lark.Token) -> ast.Universe:  # noqa: N802
        """Transform a universe name token into an AST node."""
        return ast.Universe(
            name=str(token),
            position=ast.SourcePosition.from_token(token),
        )

    @v_args(meta=True)
    def authority(
        self, meta: lark.tree.Meta, items: list[str | list[str]]
    ) -> ast.Authority:
        """Transform an authority (domain with optional path)."""
        domain = cast("str", items[0])
        path = cast("list[str]", items[1]) if len(items) == 2 else []
        return ast.Authority(
            domain=domain,
            path=path,
            position=ast.SourcePosition.from_meta(meta),
        )

    def authority_path(self, items: list[str]) -> list[str]:
        """Transform authority path segments."""
        return items

    def global_name_path(self, items: list[str]) -> list[str]:
        """Transform global name path segments."""
        return items

    def NEWLINE(self, _token: lark.Token) -> object:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return Discard
