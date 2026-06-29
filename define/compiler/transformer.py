"""Lark transformer to convert parse tree to AST nodes."""

from __future__ import annotations

import functools
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from define.compiler import ast, name_parser
from define.compiler.lark import lark_standalone

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import PurePosixPath

type _LocatedItem = ast.ASTNode | lark_standalone.Token

# Hoisted out of the per-item filter loop to avoid a global+attribute lookup on
# every item across the millions of rule reductions in a large parse.
_DISCARD = lark_standalone.Discard


def _strip_discard[Items, Result](
    method: Callable[[DefineTransformer, list[Items]], Result],
) -> Callable[[DefineTransformer, list[Items]], Result]:
    """Filter ``Discard`` out of a rule callback's items before it runs.

    Lark's inline (parse-time) transform does not auto-filter the ``Discard``
    singleton returned by token and ``terminator`` callbacks, so each rule
    callback's body would otherwise see it in its items.
    """

    @functools.wraps(method)
    def wrapper(self: DefineTransformer, items: list[Items]) -> Result:
        return method(self, [item for item in items if item is not _DISCARD])

    return wrapper


class _ParseContext(threading.local):
    """Per-parse, per-thread context for the shared inline transformer."""

    file_path: PurePosixPath | None = None
    enclosing_fqun: ast.Fqun | None = None


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
    block_close: lark_standalone.Token


@dataclass(frozen=True, slots=True)
class _LocalPositionBlockData:
    constraints: ast.PositionConstraintBlock
    block_close: lark_standalone.Token


class DefineTransformer(
    lark_standalone.Transformer[lark_standalone.Token, ast.Program]
):
    """Builds an AST inline as the Lark parser reduces each rule."""

    _context: _ParseContext

    def __init__(self):
        """Initialize the shared per-parse context."""
        super().__init__()
        self._context = _ParseContext()

    def set_file_path(self, file_path: PurePosixPath | None):
        """Set the per-parse context immediately before a parse begins.

        ``enclosing_fqun`` is reset so the namespace exists; the first
        definition's name callback always overwrites it before any body
        reference reads it.
        """
        self._context.file_path = file_path
        self._context.enclosing_fqun = None

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        """The FQUN of the definition currently being transformed."""
        if self._context.enclosing_fqun is None:
            raise ValueError(
                "tried to transform a name refeence before reading the enclosing definition name"
            )
        return self._context.enclosing_fqun

    @_strip_discard
    def start(self, items: list[ast.QualityDefinition]) -> ast.Program:
        """Assemble the top-level definitions into a Program."""
        if items:
            location = ast.SourceLocation.from_ast_or_token(
                start=items[0],
                end=items[-1],
                file_path=self._context.file_path,
            )
        else:
            location = ast.start_of_file_location(self._context.file_path)
        return ast.Program(definitions=tuple(items), location=location)

    @_strip_discard
    def global_name_definition_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.DefinitionGlobalNameContent:
        """Parse definition-site name content into a global definition node.

        This rule reduces only at definition sites, before any of the
        definition's body references reduce, so recording the enclosing FQUN
        here is what makes it available to those later reference callbacks.
        """
        result = name_parser.parse_global_name_definition(
            items[0], self._context.file_path
        )
        self._context.enclosing_fqun = result.fqun
        return result

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
            file_path=self._context.file_path,
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

    @_strip_discard
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
                location=self._location(start=keyword, end=block_data.block_close),
            )
        return ast.PositionDefinition(
            name=name,
            quality_implications=(),
            constraints=None,
            location=self._location_for_bare_definition(start=keyword, name=name),
        )

    @_strip_discard
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
        return _DISCARD

    # Many terminals are used to get their locations, for SourceLocation construction.
    # Those terminals all use the lark transformer __default__ method that just returns
    # a new copy of the token (and thus have no method here).
    #
    # The tokens below are the exception -- they never anchor a location,
    # so they are discarded.

    def TO(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard the 'to' keyword token."""
        return _DISCARD

    def CHAIN_SEPARATOR(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard chain separator tokens."""
        return _DISCARD

    def SPACE_AND_OPEN_BRACE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Discard opening braces."""
        return _DISCARD

    def NEWLINE(self, _token: lark_standalone.Token) -> object:  # noqa: N802
        """Drop newline tokens from the parse tree."""
        return _DISCARD

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
    def potential_position_definition_block(
        self,
        items: list[
            lark_standalone.Token
            | ast.QualityImplicationStatement
            | ast.PositionConstraintBlock
        ],
    ) -> _PotentialPositionBlockData:
        """Bundle the block's contents with the outer ``}`` token.

        items: [*quality_implications, position_constraint_block, CLOSE_BRACE token].
        """
        close_brace = cast("lark_standalone.Token", items[-1])
        quality_implications: list[ast.QualityImplicationStatement] = []
        constraints: ast.PositionConstraintBlock | None = None
        for item in items[:-1]:
            if isinstance(item, ast.QualityImplicationStatement):
                quality_implications.append(item)
            elif isinstance(item, ast.PositionConstraintBlock):
                constraints = item
        return _PotentialPositionBlockData(
            quality_implications=tuple(quality_implications),
            constraints=constraints,
            block_close=close_brace,
        )

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
    def position_reference(
        self, items: list[ast.TypedNameReference]
    ) -> ast.PositionReference:
        """Transform a position reference (possibly chained with ::)."""
        return ast.PositionReference(
            typed_names=tuple(items),
            location=self._location(start=items[0], end=items[-1]),
            from_source=True,
        )

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
    def constructor_condition_statement(
        self, items: list[lark_standalone.Token]
    ) -> ast.ConstructorConditionStatement:
        """Transform a constructor condition statement.

        items: [CONSTRUCTOR_STATEMENT token] (the rule has no other content).
        """
        keyword = items[0]
        return ast.ConstructorConditionStatement(
            location=self._location_with_terminator(start=keyword, end=keyword),
        )

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
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

    @_strip_discard
    def definition(self, items: list[ast.QualityDefinition]) -> ast.QualityDefinition:
        """Unwrap the definition wrapper rule."""
        return items[0]

    @_strip_discard
    def global_name_reference_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.ReferenceGlobalNameContent:
        """Parse reference-site name content into a global reference node."""
        return name_parser.parse_global_name_reference(
            items[0], self._context.file_path
        )

    @_strip_discard
    def local_name_content(
        self, items: list[lark_standalone.Token]
    ) -> ast.LocalNameContent:
        """Parse local-name content into a local-name node."""
        return name_parser.parse_local_name(items[0], self._context.file_path)
