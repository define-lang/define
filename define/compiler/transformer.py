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
        self,
        meta: lark.tree.Meta,
        items: list[ast.GlobalName | ast.ActionDefinitionBlock],
    ) -> ast.ActionDefinition:
        """Transform an action definition."""
        name = cast("ast.GlobalName", items[0])
        definition_block = (
            cast("ast.ActionDefinitionBlock", items[1]) if len(items) > 1 else None
        )
        return ast.ActionDefinition(
            name=name,
            definition_block=definition_block,
            position=ast.SourcePosition.from_meta(meta),
        )

    def terminator(self, _items: list[object]) -> object:
        """Remove terminator trees from the parse tree."""
        return Discard

    def block(self, _items: list[object]) -> object:
        """Remove empty block trees from the parse tree."""
        return Discard

    def LOCAL_NAME(self, token: lark.Token) -> ast.LocalName:  # noqa: N802
        """Transform a local name token into an AST node."""
        return ast.LocalName(
            name=token,
            position=ast.SourcePosition.from_token(token),
        )

    @v_args(meta=True)
    def local_position_definition(
        self, meta: lark.tree.Meta, items: list[ast.LocalName]
    ) -> ast.LocalPositionDefinition:
        """Transform a local position definition."""
        return ast.LocalPositionDefinition(
            local_name=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def trigger_conditions_block(
        self, meta: lark.tree.Meta, _items: list[object]
    ) -> ast.TriggerConditionsBlock:
        """Transform a trigger conditions block."""
        return ast.TriggerConditionsBlock(
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def action_statements_block(
        self, meta: lark.tree.Meta, _items: list[object]
    ) -> ast.ActionStatementsBlock:
        """Transform an action statements block."""
        return ast.ActionStatementsBlock(
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def action_definition_block(
        self,
        meta: lark.tree.Meta,
        items: list[
            ast.LocalPositionDefinition
            | ast.TriggerConditionsBlock
            | ast.ActionStatementsBlock
        ],
    ) -> ast.ActionDefinitionBlock:
        """Transform an action definition block."""
        action_statements = cast("ast.ActionStatementsBlock", items[-1])
        trigger_conditions = cast("ast.TriggerConditionsBlock", items[-2])
        local_definitions = cast("list[ast.LocalPositionDefinition]", list(items[:-2]))
        return ast.ActionDefinitionBlock(
            local_definitions=local_definitions,
            trigger_conditions=trigger_conditions,
            action_statements=action_statements,
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
            name=token,
            position=ast.SourcePosition.from_token(token),
        )

    def UNIVERSE_NAME(self, token: lark.Token) -> ast.Universe:  # noqa: N802
        """Transform a universe name token into an AST node."""
        return ast.Universe(
            name=token,
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
