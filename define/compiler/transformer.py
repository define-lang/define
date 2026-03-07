"""Lark transformer to convert parse tree to AST nodes."""

from typing import cast

from define.compiler import ast, name_parser
from define.compiler.lark import lark_standalone


class DefineTransformer(
    lark_standalone.Transformer[lark_standalone.Token, ast.Program]
):
    """Transforms the parse tree from Parser into AST nodes."""

    @lark_standalone.v_args(meta=True)
    def start(
        self, meta: lark_standalone.Meta, items: list[ast.QualityDefinition]
    ) -> ast.Program:
        """Transform the root rule into a Program."""
        return ast.Program(
            definitions=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def position_definition(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.DefinitionGlobalNameContent | ast.PositionConstraintBlock],
    ) -> ast.PositionDefinition:
        """Transform a position definition."""
        name = cast("ast.DefinitionGlobalNameContent", items[0])
        constraints = (
            cast("ast.PositionConstraintBlock", items[1]) if len(items) > 1 else None
        )
        return ast.PositionDefinition(
            name=name,
            constraints=constraints,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def action_definition(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.DefinitionGlobalNameContent | ast.ActionDefinitionBlock],
    ) -> ast.ActionDefinition:
        """Transform an action definition."""
        name = cast("ast.DefinitionGlobalNameContent", items[0])
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
        return lark_standalone.Discard

    def GLOBAL_NAME_CONTENT(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass through raw name content tokens for context-specific parsing."""
        return token

    def LOCAL_NAME_CONTENT(self, token: lark_standalone.Token) -> lark_standalone.Token:  # noqa: N802
        """Pass through raw local name content tokens for context-specific parsing."""
        return token

    def DEFINE_THE_POSITION(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the local-position definition keyword token."""
        return lark_standalone.Discard

    def DEFINE_THE_POTENTIAL_POSITION(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the potential-position definition keyword token."""
        return lark_standalone.Discard

    def DEFINE_THE_POTENTIAL_ACTION(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the potential-action definition keyword token."""
        return lark_standalone.Discard

    def IT_MAY_ONLY_CONTAIN_DIMENSION_POINTS_WHERE(  # noqa: N802
        self, _token: lark_standalone.Token
    ) -> object:
        """Discard the position-constraint intro keyword token."""
        return lark_standalone.Discard

    def IT_HAS_THE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the position-requirement keyword token."""
        return lark_standalone.Discard

    def IT_HAPPENS_WHEN(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the trigger-conditions keyword token."""
        return lark_standalone.Discard

    def THE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the trigger-condition 'the' keyword token."""
        return lark_standalone.Discard

    def HAS_A_DIMENSION_POINT(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the 'has a dimension point' keyword token."""
        return lark_standalone.Discard

    def AND_IT_DOES(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the action-statements keyword token."""
        return lark_standalone.Discard

    def CREATE_A_DIMENSION_POINT_IN(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the create-dimension-point keyword token."""
        return lark_standalone.Discard

    def MOVE_THE_DIMENSION_POINT_IN(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the move-dimension-point keyword token."""
        return lark_standalone.Discard

    def TO(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the 'to' keyword token."""
        return lark_standalone.Discard

    def CHAIN_SEPARATOR(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard chain separator tokens."""
        return lark_standalone.Discard

    def SPACE_AND_OPEN_BRACE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard opening braces."""
        return lark_standalone.Discard

    @lark_standalone.v_args(meta=True)
    def local_position_definition(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.LocalNameContent | ast.PositionConstraintBlock],
    ) -> ast.LocalPositionDefinition:
        """Transform a local position definition."""
        local_name = cast("ast.LocalNameContent", items[0])
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
            return lark_standalone.Discard
        return items[0]

    def local_position_definition_block(
        self, items: list[ast.PositionConstraintBlock]
    ) -> ast.PositionConstraintBlock:
        """Unwrap a local position definition block."""
        return items[0]

    @lark_standalone.v_args(meta=True)
    def position_constraint_block(
        self, meta: lark_standalone.Meta, items: list[ast.PositionRequirementStatement]
    ) -> ast.PositionConstraintBlock:
        """Transform a position constraint block."""
        return ast.PositionConstraintBlock(
            requirements=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def position_requirement_statement(
        self, meta: lark_standalone.Meta, items: list[ast.GlobalTypedNameReference]
    ) -> ast.PositionRequirementStatement:
        """Transform a position requirement statement."""
        return ast.PositionRequirementStatement(
            typed_global_name=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    def NAME_TYPE(self, token: lark_standalone.Token) -> ast.NameType:  # noqa: N802
        """Transform a name-type token into a NameType enum."""
        return ast.NameType(token)

    @lark_standalone.v_args(meta=True)
    def typed_global_name_reference(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.NameType | ast.ReferenceGlobalNameContent],
    ) -> ast.GlobalTypedNameReference:
        """Transform typed global name references."""
        name_type = cast("ast.NameType", items[0])
        name_content = cast("ast.ReferenceGlobalNameContent", items[1])
        return ast.GlobalTypedNameReference(
            name_type=name_type,
            name_content=name_content,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def typed_local_name_reference(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.NameType | ast.LocalNameContent],
    ) -> ast.LocalTypedNameReference:
        """Transform typed local name references."""
        name_type = cast("ast.NameType", items[0])
        name_content = cast("ast.LocalNameContent", items[1])
        return ast.LocalTypedNameReference(
            name_type=name_type,
            name_content=name_content,
            position=ast.SourcePosition.from_meta(meta),
        )

    def typed_name_reference(self, items: list[ast.TypedName]) -> ast.TypedName:
        """Unwrap the typed name reference wrapper rule."""
        return items[0]

    @lark_standalone.v_args(meta=True)
    def position_reference(
        self, meta: lark_standalone.Meta, items: list[ast.TypedNameReference]
    ) -> ast.PositionReference:
        """Transform a position reference (possibly chained with ::)."""
        return ast.PositionReference(
            chain=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def create_dimension_point_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.CreateDimensionPointStatement:
        """Transform a create dimension point statement."""
        return ast.CreateDimensionPointStatement(
            position_reference=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def move_dimension_point_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.MoveDimensionPointStatement:
        """Transform a move dimension point statement."""
        return ast.MoveDimensionPointStatement(
            from_position=items[0],
            to_position=items[1],
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def trigger_condition_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.TriggerConditionStatement:
        """Transform a trigger condition statement."""
        return ast.TriggerConditionStatement(
            position_reference=items[0],
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def trigger_conditions_block(
        self, meta: lark_standalone.Meta, items: list[ast.TriggerConditionStatement]
    ) -> ast.TriggerConditionsBlock:
        """Transform a trigger conditions block."""
        return ast.TriggerConditionsBlock(
            conditions=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def action_statements_block(
        self, meta: lark_standalone.Meta, items: list[ast.ActionStatement]
    ) -> ast.ActionStatementsBlock:
        """Transform an action statements block."""
        return ast.ActionStatementsBlock(
            statements=items,
            position=ast.SourcePosition.from_meta(meta),
        )

    @lark_standalone.v_args(meta=True)
    def action_definition_block(
        self,
        meta: lark_standalone.Meta,
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

    def global_name_definition_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.DefinitionGlobalNameContent:
        """Parse definition-site name content into a global definition node."""
        return name_parser.parse_global_name_definition(items[0])

    def global_name_reference_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.ReferenceGlobalNameContent:
        """Parse reference-site name content into a global reference node."""
        return name_parser.parse_global_name_reference(items[0])

    def local_name_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.LocalNameContent:
        """Parse local-name content into a local-name node."""
        return name_parser.parse_local_name(items[0])

    def NEWLINE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return lark_standalone.Discard
