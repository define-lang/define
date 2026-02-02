"""Lark transformer to convert parse tree to AST nodes."""

from typing import cast

import lark
from lark.visitors import Discard, _DiscardType

from compiler import ast


class DefineTransformer(lark.Transformer):
    """Transforms the parse tree from Parser into AST nodes."""

    def start(self, items: list[ast.QualityDefinition]) -> ast.Program:
        """Transform the root rule into a Program."""
        return ast.Program(items)

    def position_definition(
        self, items: list[ast.GlobalName]
    ) -> ast.PositionDefinition:
        """Transform a position definition."""
        return ast.PositionDefinition(items[0])

    def action_definition(self, items: list[ast.GlobalName]) -> ast.ActionDefinition:
        """Transform an action definition."""
        return ast.ActionDefinition(items[0])

    def global_name(self, items: list[ast.Fqun | list[str]]) -> ast.GlobalName:
        """Transform a global name with FQUN and path."""
        fqun = cast("ast.Fqun", items[0])
        path = cast("list[str]", items[1])
        return ast.GlobalName(fqun=fqun, path=path)

    def fqun(self, items: list[str | ast.Authority]) -> ast.Fqun:
        """Transform a fully-qualified universe name."""
        match len(items):
            case 3:
                return ast.Fqun(
                    multiverse=cast("str", items[0]),
                    authority=cast("ast.Authority", items[1]),
                    universe=cast("str", items[2]),
                )
            case 2:
                return ast.Fqun(
                    multiverse=None,
                    authority=cast("ast.Authority", items[0]),
                    universe=cast("str", items[1]),
                )
            case 1:
                return ast.Fqun(
                    multiverse=None,
                    authority=None,
                    universe=cast("str", items[0]),
                )
            case _:
                raise ValueError(f"Unexpected fqun items: {items}")

    def authority(self, items: list[str | list[str]]) -> ast.Authority:
        """Transform an authority (domain with optional path)."""
        domain = cast("str", items[0])
        path = cast("list[str]", items[1]) if len(items) == 2 else []
        return ast.Authority(domain=domain, path=path)

    def authority_path(self, items: list[str]) -> list[str]:
        """Transform authority path segments."""
        return items

    def global_name_path(self, items: list[str]) -> list[str]:
        """Transform global name path segments."""
        return items

    def NEWLINE(self, _token: lark.Token) -> _DiscardType:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return Discard
