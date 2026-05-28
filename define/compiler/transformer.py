"""Lark transformer to convert parse tree to AST nodes."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast

from define.compiler import ast, name_parser
from define.compiler.lark import lark_standalone

type _LocatedItem = ast.ASTNode | lark_standalone.Token


@dataclass(frozen=True, slots=True)
class _ActionDefinitionBlockData:
    quality_implications: tuple[ast.QualityImplicationStatement, ...]
    interface_positions: tuple[ast.LocalPositionDefinition, ...]
    trigger_conditions: ast.TriggerConditionsBlock
    action_statements: ast.ActionStatementsBlock
    block_close: lark_standalone.Token


@dataclass(frozen=True, slots=True)
class _PotentialPositionBlockData:
    quality_implications: tuple[ast.QualityImplicationStatement, ...]
    constraints: ast.PositionConstraintBlock | None
    initialization: ast.PositionInitBlock | None
    block_close: lark_standalone.Token


@dataclass(frozen=True, slots=True)
class _LocalPositionBlockData:
    constraints: ast.PositionConstraintBlock
    block_close: lark_standalone.Token


class DefineTransformer:
    """Top-level orchestrator that transforms a parse tree into an AST Program."""

    _file_path: PurePosixPath | None

    def __init__(self, file_path: PurePosixPath | None = None):
        """Initialize with an optional file path for source locations."""
        self._file_path = file_path

    def transform(
        self, tree: lark_standalone.Tree[lark_standalone.Token]
    ) -> ast.Program:
        """Transform the parse tree into an AST Program."""
        definitions: list[ast.QualityDefinition] = []
        for child in tree.children:
            if not isinstance(child, lark_standalone.Tree):
                continue
            enclosing_fqun = _extract_definition_fqun(child, self._file_path)
            sub_transformer = DefinitionTransformer(
                file_path=self._file_path, enclosing_fqun=enclosing_fqun
            )
            definitions.append(sub_transformer.transform(child))
        if definitions:
            location = ast.SourceLocation.from_ast_or_token(
                start=definitions[0],
                end=definitions[-1],
                file_path=self._file_path,
            )
        else:
            location = ast.start_of_file_location(self._file_path)
        return ast.Program(
            definitions=tuple(definitions),
            location=location,
        )


def _extract_definition_fqun(
    definition_tree: lark_standalone.Tree[lark_standalone.Token],
    file_path: PurePosixPath | None,
) -> ast.Fqun:
    """Extract the inline FQUN from a definition parse subtree."""
    inner = cast(
        "lark_standalone.Tree[lark_standalone.Token]", definition_tree.children[0]
    )
    name_tree = cast("lark_standalone.Tree[lark_standalone.Token]", inner.children[1])
    name_token = cast("lark_standalone.Token", name_tree.children[0])
    return name_parser.parse_global_name_definition(name_token, file_path).fqun


class DefinitionTransformer(
    lark_standalone.Transformer[lark_standalone.Token, ast.QualityDefinition]
):
    """Transforms a single definition subtree into an AST QualityDefinition."""

    _file_path: PurePosixPath | None
    _enclosing_fqun: ast.Fqun

    def __init__(
        self,
        *,
        file_path: PurePosixPath | None,
        enclosing_fqun: ast.Fqun,
    ):
        """Initialize with the enclosing definition's FQUN and an optional file path."""
        super().__init__()
        self._file_path = file_path
        self._enclosing_fqun = enclosing_fqun

    def _location(
        self,
        *,
        start: _LocatedItem,
        end: _LocatedItem,
        end_column_offset: int = 0,
    ) -> ast.SourceLocation:
        return ast.SourceLocation.from_ast_or_token(
            start=start,
            end=end,
            file_path=self._file_path,
            end_column_offset=end_column_offset,
        )

    def _location_with_terminator(
        self, *, start: _LocatedItem, end: _LocatedItem
    ) -> ast.SourceLocation:
        """Span ``start..end`` plus the trailing ``.`` terminator.

        The terminator rule returns ``Discard`` so the period is not in items;
        extend ``end_column`` by one to include it.
        """
        return self._location(start=start, end=end, end_column_offset=1)

    def _location_for_bare_definition(
        self, *, start: _LocatedItem, name: ast.NameContent
    ) -> ast.SourceLocation:
        """Span a bare ``<keyword> <name>.`` definition.

        ``NameContent.location`` covers only the inner name token, so two
        extra columns are needed: one for the closing ``>`` of the name,
        and one for the trailing ``.`` terminator.
        """
        return self._location(start=start, end=name, end_column_offset=2)

    def position_definition(
        self,
        items: list[
            lark_standalone.Token
            | ast.DefinitionGlobalNameContent
            | _PotentialPositionBlockData
        ],
    ) -> ast.PositionDefinition:
        """Transform a position definition.

        items: [DEFINE_THE_POTENTIAL_POSITION token, name, optional block data].
        """
        keyword = cast("lark_standalone.Token", items[0])
        name = cast("ast.DefinitionGlobalNameContent", items[1])
        if len(items) > 2:
            block_data = cast("_PotentialPositionBlockData", items[2])
            return ast.PositionDefinition(
                name=name,
                quality_implications=block_data.quality_implications,
                constraints=block_data.constraints,
                initialization=block_data.initialization,
                location=self._location(start=keyword, end=block_data.block_close),
            )
        return ast.PositionDefinition(
            name=name,
            quality_implications=(),
            constraints=None,
            initialization=None,
            location=self._location_for_bare_definition(start=keyword, name=name),
        )

    def action_definition(
        self,
        items: list[
            lark_standalone.Token
            | ast.DefinitionGlobalNameContent
            | _ActionDefinitionBlockData
        ],
    ) -> ast.ActionDefinition:
        """Transform an action definition.

        items: [DEFINE_THE_POTENTIAL_ACTION token, name, action block data].
        """
        keyword = cast("lark_standalone.Token", items[0])
        name = cast("ast.DefinitionGlobalNameContent", items[1])
        block_data = cast("_ActionDefinitionBlockData", items[2])
        return ast.ActionDefinition(
            name=name,
            quality_implications=block_data.quality_implications,
            interface_positions=block_data.interface_positions,
            trigger_conditions=block_data.trigger_conditions,
            action_statements=block_data.action_statements,
            location=self._location(start=keyword, end=block_data.block_close),
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

    # Keyword tokens are passed through (not discarded). Each one anchors the
    # location of its enclosing rule's AST node: without lark's
    # PropagatePositions to populate Tree.meta, the rule derives its
    # SourceLocation by scanning items, and these tokens carry the line/column
    # of the rule's leading keyword. Each rule reads its data from later items
    # by index.

    def CLOSE_BRACE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the block-closing ``}`` token through.

        Block rules use it as their end-location anchor.
        """
        return token

    def DEFINE_THE_POSITION(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the local-position definition keyword token through."""
        return token

    def DEFINE_THE_POTENTIAL_POSITION(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the potential-position definition keyword token through."""
        return token

    def DEFINE_THE_POTENTIAL_ACTION(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the potential-action definition keyword token through."""
        return token

    def IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the position-constraint intro keyword token through."""
        return token

    def IT_HAS_THE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the position-requirement keyword token through."""
        return token

    def IT_ALSO_ASSIGNS_THE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the quality-implication keyword token through."""
        return token

    def IT_HAPPENS_WHEN(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the trigger-conditions keyword token through."""
        return token

    def THE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the trigger-condition 'the' keyword token through."""
        return token

    def HAS_A_PARTICLE(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the 'has a particle' keyword token through."""
        return token

    def DESTRUCTOR_STATEMENT(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the destructor-condition keyword token through."""
        return token

    def AND_IT_DOES(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the action-statements keyword token through."""
        return token

    def CREATE_A_PARTICLE_IN(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the create-particle keyword token through."""
        return token

    def MOVE_THE_PARTICLE_IN(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the move-particle keyword token through."""
        return token

    def DESTROY_THE_PARTICLE_IN(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the destroy-particle keyword token through."""
        return token

    def AFTER_IT_IS_ASSIGNED(  # noqa: N802
        self, token: lark_standalone.Token
    ) -> lark_standalone.Token:
        """Pass the init-block keyword token through."""
        return token

    # These three tokens never anchor a rule location: TO sits between the
    # source and target of a move (the move keyword is the anchor),
    # CHAIN_SEPARATOR sits between chain elements, and SPACE_AND_OPEN_BRACE
    # is the body-block opener.

    def TO(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the 'to' keyword token."""
        return lark_standalone.Discard

    def CHAIN_SEPARATOR(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard chain separator tokens."""
        return lark_standalone.Discard

    def SPACE_AND_OPEN_BRACE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard opening braces."""
        return lark_standalone.Discard

    def local_position_definition(
        self,
        items: list[
            lark_standalone.Token | ast.LocalNameContent | _LocalPositionBlockData
        ],
    ) -> ast.LocalPositionDefinition:
        """Transform a local position definition.

        items: [DEFINE_THE_POSITION token, local_name, optional block data].
        """
        keyword = cast("lark_standalone.Token", items[0])
        local_name = cast("ast.LocalNameContent", items[1])
        if len(items) > 2:
            block_data = cast("_LocalPositionBlockData", items[2])
            return ast.LocalPositionDefinition(
                local_name=local_name,
                constraints=block_data.constraints,
                location=self._location(start=keyword, end=block_data.block_close),
            )
        return ast.LocalPositionDefinition(
            local_name=local_name,
            constraints=None,
            location=self._location_for_bare_definition(start=keyword, name=local_name),
        )

    def position_definition_terminator_or_block(
        self, items: list[ast.PositionConstraintBlock]
    ) -> ast.PositionConstraintBlock | object:
        """Unwrap an optional position-definition ending block."""
        if not items:
            return lark_standalone.Discard
        return items[0]

    def local_position_definition_block(
        self,
        items: list[lark_standalone.Token | ast.PositionConstraintBlock],
    ) -> _LocalPositionBlockData:
        """Bundle the inner constraint block with the outer ``}`` token.

        items: [position_constraint_block, CLOSE_BRACE token].
        """
        return _LocalPositionBlockData(
            constraints=cast("ast.PositionConstraintBlock", items[0]),
            block_close=cast("lark_standalone.Token", items[1]),
        )

    def potential_position_definition_block(
        self,
        items: list[
            lark_standalone.Token
            | ast.QualityImplicationStatement
            | ast.PositionConstraintBlock
            | ast.PositionInitBlock
            | None
        ],
    ) -> _PotentialPositionBlockData:
        """Bundle the block's contents with the outer ``}`` token.

        items: [*quality_implications, position_constraint_block?, position_initialization_block?, CLOSE_BRACE token].
        Lark's maybe_placeholders may insert ``None`` for the absent optional
        position_initialization_block; those entries are skipped.
        """
        close_brace = cast("lark_standalone.Token", items[-1])
        quality_implications: list[ast.QualityImplicationStatement] = []
        constraints: ast.PositionConstraintBlock | None = None
        initialization: ast.PositionInitBlock | None = None
        for item in items[:-1]:
            if item is None:
                continue
            if isinstance(item, ast.QualityImplicationStatement):
                quality_implications.append(item)
            elif isinstance(item, ast.PositionConstraintBlock):
                constraints = item
            elif isinstance(item, ast.PositionInitBlock):
                initialization = item
        return _PotentialPositionBlockData(
            quality_implications=tuple(quality_implications),
            constraints=constraints,
            initialization=initialization,
            block_close=close_brace,
        )

    def position_initialization_block(
        self,
        items: list[lark_standalone.Token | ast.ActionStatement],
    ) -> ast.PositionInitBlock:
        """Transform a position init block.

        items: [AFTER_IT_IS_ASSIGNED token, *statements, CLOSE_BRACE token].
        """
        keyword = cast("lark_standalone.Token", items[0])
        close_brace = cast("lark_standalone.Token", items[-1])
        statements = cast("list[ast.ActionStatement]", items[1:-1])
        return ast.PositionInitBlock(
            statements=tuple(statements),
            location=self._location(start=keyword, end=close_brace),
        )

    def position_constraint_block(
        self,
        items: list[lark_standalone.Token | ast.PositionRequirementStatement],
    ) -> ast.PositionConstraintBlock:
        """Transform a position constraint block.

        items: [IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE token, *requirements,
        CLOSE_BRACE token].
        """
        keyword = cast("lark_standalone.Token", items[0])
        close_brace = cast("lark_standalone.Token", items[-1])
        requirements = cast("list[ast.PositionRequirementStatement]", items[1:-1])
        return ast.PositionConstraintBlock(
            requirements=tuple(requirements),
            location=self._location(start=keyword, end=close_brace),
        )

    def position_requirement_statement(
        self,
        items: list[lark_standalone.Token | ast.GlobalTypedNameReference],
    ) -> ast.PositionRequirementStatement:
        """Transform a position requirement statement.

        items: [IT_HAS_THE token, typed_global_name_reference].
        """
        keyword = cast("lark_standalone.Token", items[0])
        typed_global_name = cast("ast.GlobalTypedNameReference", items[1])
        return ast.PositionRequirementStatement(
            typed_global_name=typed_global_name,
            location=self._location_with_terminator(
                start=keyword, end=typed_global_name
            ),
        )

    def quality_implication_statement(
        self,
        items: list[lark_standalone.Token | ast.GlobalTypedNameReference],
    ) -> ast.QualityImplicationStatement:
        """Transform a quality implication statement.

        items: [IT_ALSO_ASSIGNS_THE token, typed_global_name_reference].
        """
        keyword = cast("lark_standalone.Token", items[0])
        typed_global_name = cast("ast.GlobalTypedNameReference", items[1])
        return ast.QualityImplicationStatement(
            typed_global_name=typed_global_name,
            location=self._location_with_terminator(
                start=keyword, end=typed_global_name
            ),
        )

    def NAME_TYPE(self, token: lark_standalone.Token) -> ast.NameType:  # noqa: N802
        """Transform a name-type token into a NameType enum."""
        return ast.NameType(token)

    def typed_global_name_reference(
        self,
        items: list[ast.NameType | ast.ReferenceGlobalNameContent],
    ) -> ast.GlobalTypedNameReference:
        """Transform typed global name references."""
        name_type = cast("ast.NameType", items[0])
        name_content = cast("ast.ReferenceGlobalNameContent", items[1])
        return ast.GlobalTypedNameReference(
            name_type=name_type,
            name_content=name_content,
            enclosing_fqun=self._enclosing_fqun,
            location=ast.SourceLocation.from_definition_name(name_content, name_type),
        )

    def typed_local_name_reference(
        self,
        items: list[ast.NameType | ast.LocalNameContent],
    ) -> ast.LocalTypedNameReference:
        """Transform typed local name references."""
        name_type = cast("ast.NameType", items[0])
        name_content = cast("ast.LocalNameContent", items[1])
        return ast.LocalTypedNameReference(
            name_type=name_type,
            name_content=name_content,
            location=ast.SourceLocation.from_definition_name(name_content, name_type),
        )

    def typed_name_reference(self, items: list[ast.TypedName]) -> ast.TypedName:
        """Unwrap the typed name reference wrapper rule."""
        return items[0]

    def position_reference(
        self, items: list[ast.TypedNameReference]
    ) -> ast.PositionReference:
        """Transform a position reference (possibly chained with ::)."""
        return ast.PositionReference(
            typed_names=tuple(items),
            location=self._location(start=items[0], end=items[-1]),
            from_source=True,
        )

    def create_particle_statement(
        self, items: list[lark_standalone.Token | ast.PositionReference]
    ) -> ast.CreateParticleStatement:
        """Transform a create particle statement.

        items: [CREATE_A_PARTICLE_IN token, position_reference].
        """
        keyword = cast("lark_standalone.Token", items[0])
        target = cast("ast.PositionReference", items[1])
        return ast.CreateParticleStatement(
            target_position=target,
            location=self._location_with_terminator(start=keyword, end=target),
        )

    def move_particle_statement(
        self, items: list[lark_standalone.Token | ast.PositionReference]
    ) -> ast.MoveParticleStatement:
        """Transform a move particle statement.

        items: [MOVE_THE_PARTICLE_IN token, source_position, target_position].
        The TO separator between source and target is discarded.
        """
        keyword = cast("lark_standalone.Token", items[0])
        source = cast("ast.PositionReference", items[1])
        target = cast("ast.PositionReference", items[2])
        return ast.MoveParticleStatement(
            source_position=source,
            target_position=target,
            location=self._location_with_terminator(start=keyword, end=target),
        )

    def destroy_particle_statement(
        self, items: list[lark_standalone.Token | ast.PositionReference]
    ) -> ast.DestroyParticleStatement:
        """Transform a destroy particle statement.

        items: [DESTROY_THE_PARTICLE_IN token, position_reference].
        """
        keyword = cast("lark_standalone.Token", items[0])
        target = cast("ast.PositionReference", items[1])
        return ast.DestroyParticleStatement(
            target_position=target,
            location=self._location_with_terminator(start=keyword, end=target),
        )

    def position_presence_statement(
        self, items: list[lark_standalone.Token | ast.LocalTypedNameReference]
    ) -> ast.PositionPresenceStatement:
        """Transform a position presence statement.

        items: [THE token, typed_local_name_reference, HAS_A_PARTICLE token].
        """
        the_keyword = cast("lark_standalone.Token", items[0])
        typed_name = cast("ast.LocalTypedNameReference", items[1])
        has_a_particle = cast("lark_standalone.Token", items[2])
        return ast.PositionPresenceStatement(
            typed_name=typed_name,
            location=self._location_with_terminator(
                start=the_keyword, end=has_a_particle
            ),
        )

    def destructor_condition_statement(
        self, items: list[lark_standalone.Token]
    ) -> ast.DestructorConditionStatement:
        """Transform a destructor condition statement.

        items: [DESTRUCTOR_STATEMENT token] (the rule has no other content).
        """
        keyword = items[0]
        return ast.DestructorConditionStatement(
            location=self._location_with_terminator(start=keyword, end=keyword),
        )

    def trigger_condition_statement(
        self, items: list[ast.TriggerConditionStatement]
    ) -> ast.TriggerConditionStatement:
        """Unwrap the trigger condition statement wrapper rule."""
        return items[0]

    def trigger_conditions_block(
        self,
        items: list[lark_standalone.Token | ast.TriggerConditionStatement],
    ) -> ast.TriggerConditionsBlock:
        """Transform a trigger conditions block.

        items: [IT_HAPPENS_WHEN token, *conditions, CLOSE_BRACE token].
        """
        keyword = cast("lark_standalone.Token", items[0])
        close_brace = cast("lark_standalone.Token", items[-1])
        conditions = cast("list[ast.TriggerConditionStatement]", items[1:-1])
        return ast.TriggerConditionsBlock(
            conditions=tuple(conditions),
            location=self._location(start=keyword, end=close_brace),
        )

    def action_statements_block(
        self, items: list[lark_standalone.Token | ast.ActionStatement]
    ) -> ast.ActionStatementsBlock:
        """Transform an action statements block.

        items: [AND_IT_DOES token, *statements, CLOSE_BRACE token].
        """
        keyword = cast("lark_standalone.Token", items[0])
        close_brace = cast("lark_standalone.Token", items[-1])
        statements = cast("list[ast.ActionStatement]", items[1:-1])
        return ast.ActionStatementsBlock(
            statements=tuple(statements),
            location=self._location(start=keyword, end=close_brace),
        )

    def action_definition_block(
        self,
        items: list[
            lark_standalone.Token
            | ast.QualityImplicationStatement
            | ast.LocalPositionDefinition
            | ast.TriggerConditionsBlock
            | ast.ActionStatementsBlock
        ],
    ) -> _ActionDefinitionBlockData:
        """Transform an action definition block.

        items: [*quality_implications, *interface_positions, trigger_conditions,
        action_statements, CLOSE_BRACE token].
        """
        close_brace = cast("lark_standalone.Token", items[-1])
        action_statements = cast("ast.ActionStatementsBlock", items[-2])
        trigger_conditions = cast("ast.TriggerConditionsBlock", items[-3])
        quality_implications: list[ast.QualityImplicationStatement] = []
        interface_positions: list[ast.LocalPositionDefinition] = []
        for item in items[:-3]:
            if isinstance(item, ast.QualityImplicationStatement):
                quality_implications.append(item)
            else:
                interface_positions.append(cast("ast.LocalPositionDefinition", item))
        return _ActionDefinitionBlockData(
            quality_implications=tuple(quality_implications),
            interface_positions=tuple(interface_positions),
            trigger_conditions=trigger_conditions,
            action_statements=action_statements,
            block_close=close_brace,
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
