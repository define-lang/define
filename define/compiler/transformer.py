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
        self,
        meta: lark.tree.Meta,
        items: list[ast.GlobalNameDefinition | ast.PositionConstraintBlock],
    ) -> ast.PositionDefinition:
        """Transform a position definition."""
        name = cast("ast.GlobalNameDefinition", items[0])
        constraints = (
            cast("ast.PositionConstraintBlock", items[1]) if len(items) > 1 else None
        )
        return ast.PositionDefinition(
            name=name,
            constraints=constraints,
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def action_definition(
        self,
        meta: lark.tree.Meta,
        items: list[ast.GlobalNameDefinition | ast.ActionDefinitionBlock],
    ) -> ast.ActionDefinition:
        """Transform an action definition."""
        name = cast("ast.GlobalNameDefinition", items[0])
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

    def PATH_SEGMENT(self, token: lark.Token) -> ast.GlobalPathNameSegment:  # noqa: N802
        """Transform a path segment token into an AST node."""
        return ast.GlobalPathNameSegment(
            name=token,
            position=ast.SourcePosition.from_token(token),
        )

    def LOCAL_NAME(self, token: lark.Token) -> ast.LocalName:  # noqa: N802
        """Transform a local name token into an AST node."""
        return ast.LocalName(
            name=token,
            position=ast.SourcePosition.from_token(token),
        )

    def DEFINE_THE_POSITION(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the local-position definition keyword token."""
        return Discard

    def DEFINE_THE_POTENTIAL_POSITION(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the potential-position definition keyword token."""
        return Discard

    def DEFINE_THE_POTENTIAL_ACTION(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the potential-action definition keyword token."""
        return Discard

    def IT_MAY_ONLY_CONTAIN_DIMENSION_POINTS_WHERE(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the position-constraint intro keyword token."""
        return Discard

    def IT_HAS_THE(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the position-requirement keyword token."""
        return Discard

    def IT_HAPPENS_WHEN(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the trigger-conditions keyword token."""
        return Discard

    def AND_IT_DOES(self, _token: lark.Token) -> object:  # noqa: N802
        """Discard the action-statements keyword token."""
        return Discard

    @v_args(meta=True)
    def local_position_definition(
        self,
        meta: lark.tree.Meta,
        items: list[ast.LocalName | ast.PositionConstraintBlock],
    ) -> ast.LocalPositionDefinition:
        """Transform a local position definition."""
        local_name = cast("ast.LocalName", items[0])
        constraints = (
            cast("ast.PositionConstraintBlock", items[1]) if len(items) > 1 else None
        )
        return ast.LocalPositionDefinition(
            local_name=local_name,
            constraints=constraints,
            position=ast.SourcePosition.from_meta(meta),
        )

    def position_definition_terminator_or_block(
        self, items: list[ast.PositionConstraintBlock]
    ) -> ast.PositionConstraintBlock | object:
        """Unwrap an optional position-definition ending block."""
        if not items:
            return Discard
        return items[0]

    def local_position_definition_block(
        self, items: list[ast.PositionConstraintBlock]
    ) -> ast.PositionConstraintBlock:
        """Unwrap a local position definition block."""
        return items[0]

    @v_args(meta=True)
    def position_constraint_block(
        self, meta: lark.tree.Meta, items: list[ast.PositionRequirementStatement]
    ) -> ast.PositionConstraintBlock:
        """Transform a position constraint block."""
        return ast.PositionConstraintBlock(
            requirements=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @v_args(meta=True)
    def position_requirement_statement(
        self, meta: lark.tree.Meta, items: list[ast.TypedGlobalNameReference]
    ) -> ast.PositionRequirementStatement:
        """Transform a position requirement statement."""
        return ast.PositionRequirementStatement(
            typed_global_name=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    def NAME_TYPE(self, token: lark.Token) -> ast.TypeName:  # noqa: N802
        """Transform a name-type token into a TypeName enum."""
        return ast.TypeName(token)

    def typed_global_name_reference(
        self, items: list[ast.TypeName | ast.GlobalNameReference]
    ) -> ast.TypedGlobalNameReference:
        """Transform typed global name references."""
        type_name = cast("ast.TypeName", items[0])
        global_name = cast("ast.GlobalNameReference", items[1])
        return ast.TypedGlobalNameReference(
            type_name=type_name,
            global_name=global_name,
            position=global_name.position,
        )

    @v_args(meta=True)
    def global_name_reference(
        self, meta: lark.tree.Meta, items: list[ast.Fqun | ast.GlobalPathName]
    ) -> ast.GlobalNameReference:
        """Transform a global name reference."""
        if len(items) == 2:
            fqun = cast("ast.Fqun", items[0])
            path = cast("ast.GlobalPathName", items[1])
        else:
            fqun = None
            path = cast("ast.GlobalPathName", items[0])
        return ast.GlobalNameReference(
            fqun=fqun,
            path=path,
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
        self, meta: lark.tree.Meta, items: list[ast.ActionStatement]
    ) -> ast.ActionStatementsBlock:
        """Transform an action statements block."""
        return ast.ActionStatementsBlock(
            statements=items,
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
        self, meta: lark.tree.Meta, items: list[ast.Fqun | ast.GlobalPathName]
    ) -> ast.GlobalNameDefinition:
        """Transform a global name with FQUN and path."""
        fqun = cast("ast.Fqun", items[0])
        path = cast("ast.GlobalPathName", items[1])
        return ast.GlobalNameDefinition(
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

    @v_args(meta=True)
    def global_name_path(
        self, meta: lark.tree.Meta, items: list[ast.GlobalPathNameSegment]
    ) -> ast.GlobalPathName:
        """Transform global name path segments."""
        return ast.GlobalPathName(
            segments=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    def NEWLINE(self, _token: lark.Token) -> object:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return Discard
