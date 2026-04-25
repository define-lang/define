"""Lark transformer to convert parse tree to AST nodes."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast

from define.compiler import ast, name_parser
from define.compiler.lark import lark_standalone


@dataclass(frozen=True, slots=True)
class _ActionDefinitionBlockData:
    quality_requirements: list[ast.QualityRequirementStatement]
    interface_positions: list[ast.LocalPositionDefinition]
    trigger_conditions: ast.TriggerConditionsBlock
    action_statements: ast.ActionStatementsBlock


class DefineTransformer(
    lark_standalone.Transformer[lark_standalone.Token, ast.Program]
):
    """Transforms the parse tree from Parser into AST nodes."""

    _file_path: PurePosixPath | None

    def __init__(self, file_path: PurePosixPath | None = None):
        """Initialize with an optional file path for source locations."""
        super().__init__()
        self._file_path = file_path

    @lark_standalone.v_args(meta=True)
    def start(
        self, meta: lark_standalone.Meta, items: list[ast.QualityDefinition]
    ) -> ast.Program:
        """Transform the root rule into a Program."""
        return ast.Program(
            definitions=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def position_definition(
        self,
        meta: lark_standalone.Meta,
        items: list[
            ast.DefinitionGlobalNameContent
            | list[
                ast.QualityRequirementStatement
                | ast.PositionConstraintBlock
                | ast.PositionInitBlock
            ]
        ],
    ) -> ast.PositionDefinition:
        """Transform a position definition."""
        name = cast("ast.DefinitionGlobalNameContent", items[0])
        quality_requirements: list[ast.QualityRequirementStatement] = []
        constraints: ast.PositionConstraintBlock | None = None
        initialization: ast.PositionInitBlock | None = None
        if len(items) > 1:
            block_contents = cast(
                "list[ast.QualityRequirementStatement | ast.PositionConstraintBlock | ast.PositionInitBlock]",
                items[1],
            )
            for item in block_contents:
                if isinstance(item, ast.QualityRequirementStatement):
                    quality_requirements.append(item)
                elif isinstance(item, ast.PositionConstraintBlock):
                    constraints = item
                else:
                    initialization = item
        return ast.PositionDefinition(
            name=name,
            quality_requirements=quality_requirements,
            constraints=constraints,
            initialization=initialization,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def action_definition(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.DefinitionGlobalNameContent | _ActionDefinitionBlockData],
    ) -> ast.ActionDefinition:
        """Transform an action definition."""
        name = cast("ast.DefinitionGlobalNameContent", items[0])
        block_data = cast("_ActionDefinitionBlockData", items[1])
        return ast.ActionDefinition(
            name=name,
            quality_requirements=block_data.quality_requirements,
            interface_positions=block_data.interface_positions,
            trigger_conditions=block_data.trigger_conditions,
            action_statements=block_data.action_statements,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
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

    def THIS_DIMENSION_POINT_MUST_HAVE_THE(  # noqa: N802
        self, _token: lark_standalone.Token
    ) -> object:
        """Discard the quality-requirement keyword token."""
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

    def DESTROY_THE_DIMENSION_POINT_IN(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the destroy-dimension-point keyword token."""
        return lark_standalone.Discard

    def TO(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the 'to' keyword token."""
        return lark_standalone.Discard

    def CHAIN_SEPARATOR(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard chain separator tokens."""
        return lark_standalone.Discard

    def AFTER_IT_IS_ASSIGNED(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the init-block keyword token."""
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
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
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

    def potential_position_definition_block(
        self,
        items: list[
            ast.QualityRequirementStatement
            | ast.PositionConstraintBlock
            | ast.PositionInitBlock
        ],
    ) -> list[
        ast.QualityRequirementStatement
        | ast.PositionConstraintBlock
        | ast.PositionInitBlock
    ]:
        """Pass through quality requirements and constraint/init blocks from a potential position definition."""
        return items

    @lark_standalone.v_args(meta=True)
    def position_initialization_block(
        self,
        meta: lark_standalone.Meta,
        items: list[ast.ActionStatement],
    ) -> ast.PositionInitBlock:
        """Transform a position init block."""
        return ast.PositionInitBlock(
            statements=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def position_constraint_block(
        self, meta: lark_standalone.Meta, items: list[ast.PositionRequirementStatement]
    ) -> ast.PositionConstraintBlock:
        """Transform a position constraint block."""
        return ast.PositionConstraintBlock(
            requirements=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def position_requirement_statement(
        self, meta: lark_standalone.Meta, items: list[ast.GlobalTypedNameReference]
    ) -> ast.PositionRequirementStatement:
        """Transform a position requirement statement."""
        return ast.PositionRequirementStatement(
            typed_global_name=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def quality_requirement_statement(
        self, meta: lark_standalone.Meta, items: list[ast.GlobalTypedNameReference]
    ) -> ast.QualityRequirementStatement:
        """Transform a quality requirement statement."""
        return ast.QualityRequirementStatement(
            typed_global_name=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
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
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
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
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
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
            typed_names=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
            from_source=True,
        )

    @lark_standalone.v_args(meta=True)
    def create_dimension_point_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.CreateDimensionPointStatement:
        """Transform a create dimension point statement."""
        return ast.CreateDimensionPointStatement(
            target_position=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def move_dimension_point_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.MoveDimensionPointStatement:
        """Transform a move dimension point statement."""
        return ast.MoveDimensionPointStatement(
            target_position=items[1],
            source_position=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def destroy_dimension_point_statement(
        self, meta: lark_standalone.Meta, items: list[ast.PositionReference]
    ) -> ast.DestroyDimensionPointStatement:
        """Transform a destroy dimension point statement."""
        return ast.DestroyDimensionPointStatement(
            target_position=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def trigger_condition_statement(
        self, meta: lark_standalone.Meta, items: list[ast.LocalTypedNameReference]
    ) -> ast.TriggerConditionStatement:
        """Transform a trigger condition statement."""
        return ast.TriggerConditionStatement(
            typed_name=items[0],
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def trigger_conditions_block(
        self, meta: lark_standalone.Meta, items: list[ast.TriggerConditionStatement]
    ) -> ast.TriggerConditionsBlock:
        """Transform a trigger conditions block."""
        return ast.TriggerConditionsBlock(
            conditions=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    @lark_standalone.v_args(meta=True)
    def action_statements_block(
        self, meta: lark_standalone.Meta, items: list[ast.ActionStatement]
    ) -> ast.ActionStatementsBlock:
        """Transform an action statements block."""
        return ast.ActionStatementsBlock(
            statements=items,
            location=ast.SourceLocation.from_meta(meta, file_path=self._file_path),
        )

    def action_definition_block(
        self,
        items: list[
            ast.QualityRequirementStatement
            | ast.LocalPositionDefinition
            | ast.TriggerConditionsBlock
            | ast.ActionStatementsBlock
        ],
    ) -> _ActionDefinitionBlockData:
        """Transform an action definition block."""
        action_statements = cast("ast.ActionStatementsBlock", items[-1])
        trigger_conditions = cast("ast.TriggerConditionsBlock", items[-2])
        quality_requirements: list[ast.QualityRequirementStatement] = []
        interface_positions: list[ast.LocalPositionDefinition] = []
        for item in items[:-2]:
            if isinstance(item, ast.QualityRequirementStatement):
                quality_requirements.append(item)
            else:
                interface_positions.append(cast("ast.LocalPositionDefinition", item))
        return _ActionDefinitionBlockData(
            quality_requirements=quality_requirements,
            interface_positions=interface_positions,
            trigger_conditions=trigger_conditions,
            action_statements=action_statements,
        )

    def definition(self, items: list[ast.QualityDefinition]) -> ast.QualityDefinition:
        """Unwrap the definition wrapper rule."""
        return items[0]

    def global_name_definition_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.DefinitionGlobalNameContent:
        """Parse definition-site name content into a global definition node."""
        return name_parser.parse_global_name_definition(items[0], self._file_path)

    def global_name_reference_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.ReferenceGlobalNameContent:
        """Parse reference-site name content into a global reference node."""
        return name_parser.parse_global_name_reference(items[0], self._file_path)

    def local_name_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.LocalNameContent:
        """Parse local-name content into a local-name node."""
        return name_parser.parse_local_name(items[0], self._file_path)

    def NEWLINE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return lark_standalone.Discard
