"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

import abc
import enum
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, override

from define.compiler import constants
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import PurePosixPath

    from define.compiler.lark import lark_standalone


class NameType(enum.StrEnum):
    """The type of a quality definition."""

    POSITION = "position"
    ACTION = "action"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Represents a location in source code."""

    line: int
    column: int
    end_line: int
    end_column: int
    file_path: PurePosixPath | None = None

    # We use this instead of Lark's propagate_positions because propogate_positions
    # was very slow (it was the #1 CPU consumer in compilation, overall).
    @classmethod
    def from_ast_or_token(
        cls,
        *,
        start: ASTNode | lark_standalone.Token,
        end: ASTNode | lark_standalone.Token,
        file_path: PurePosixPath | None = None,
        end_column_offset: int = 0,
    ) -> Self:
        """Build a SourceLocation spanning ``start`` through ``end``.

        Each argument is either an ``ASTNode`` (whose ``.location`` is read)
        or a ``lark_standalone.Token`` (whose lexer-set
        ``line``/``column``/``end_line``/``end_column`` are read). When
        ``start`` and ``end`` are the same instance, the result is that
        item's full span.
        """
        if isinstance(start, ASTNode):
            start_line = start.location.line
            start_column = start.location.column
        else:
            if start.line is None or start.column is None:
                raise ValueError(f"token {start!r} has no line/column")
            start_line = start.line
            start_column = start.column
        if isinstance(end, ASTNode):
            end_line = end.location.end_line
            end_column = end.location.end_column
        else:
            if end.end_line is None or end.end_column is None:
                raise ValueError(f"token {end!r} has no end_line/end_column")
            end_line = end.end_line
            end_column = end.end_column
        return cls(
            line=start_line,
            column=start_column,
            end_line=end_line,
            end_column=end_column + end_column_offset,
            file_path=file_path,
        )

    @classmethod
    def from_definition_name(
        cls, name_content: NameContent, name_type: NameType
    ) -> Self:
        """Source location of a typed name at its definition site.

        Spans the type-keyword word ("position" or "action") immediately
        before "<" through the closing ">" of the name content.
        """
        name_loc = name_content.location
        return cls(
            line=name_loc.line,
            column=name_loc.column - 1 - len(name_type.value),
            end_line=name_loc.end_line,
            end_column=name_loc.end_column + 1,
            file_path=name_loc.file_path,
        )


def start_of_file_location(
    file_path: PurePosixPath | None = None,
) -> SourceLocation:
    """Return a SourceLocation pointing to the very start of a file."""
    return SourceLocation(
        line=1, column=1, end_line=1, end_column=1, file_path=file_path
    )


@dataclass(frozen=True, slots=True)
class ASTNode:
    """Base class for all AST nodes."""

    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Program(ASTNode):
    """Represents the entire program."""

    definitions: tuple[QualityDefinition, ...]


@dataclass(frozen=True, slots=True)
class QualityDefinition(ASTNode):
    """Base class for quality definitions (positions and actions)."""

    typed_name: GlobalTypedNameInDefinition
    quality_implications: tuple[QualityImplicationStatement, ...]


@dataclass(frozen=True, slots=True, init=False)
class PositionDefinition(QualityDefinition):
    """Represents a position definition."""

    constraints: PositionConstraintBlock | None
    initialization: PositionInitBlock | None

    def __init__(
        self,
        *,
        name: DefinitionGlobalNameContent,
        location: SourceLocation,
        quality_implications: tuple[QualityImplicationStatement, ...] | None = None,
        constraints: PositionConstraintBlock | None = None,
        initialization: PositionInitBlock | None = None,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.POSITION,
                name_content=name,
                location=SourceLocation.from_definition_name(name, NameType.POSITION),
            ),
            quality_implications=quality_implications or (),
            location=location,
        )
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "initialization", initialization)

    @property
    def constraint_typed_names(self) -> tuple[GlobalTypedNameReference, ...]:
        """Return the typed names of this position's constraint requirements, in source order."""
        if self.constraints is None:
            return ()
        return tuple(req.typed_global_name for req in self.constraints.requirements)


@dataclass(frozen=True, slots=True)
class NameContent(ASTNode, abc.ABC):
    """Base class for name content nodes (local or global)."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Return the inner content as it appears in the source."""


@dataclass(frozen=True, slots=True)
class LocalNameContent(NameContent):
    """Represents a local name."""

    name: str

    def __post_init__(self):
        """Coerce to a plain interned str.

        The parser passes a lark Token here, which is a str subclass that
        carries extra slots (type, start_pos, line, column, ...) and is
        rejected by sys.intern. Local names like ``run`` repeat heavily
        across a program, so we drop the Token wrapper and intern the
        underlying string for sharing.
        """
        object.__setattr__(self, "name", sys.intern(str(self.name)))

    @property
    @override
    def source_name(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True, init=False)
class LocalPositionDefinition(ASTNode):
    """Represents a local position definition."""

    typed_name: LocalTypedNameReference
    constraints: PositionConstraintBlock | None

    def __init__(
        self,
        *,
        local_name: LocalNameContent,
        location: SourceLocation,
        constraints: PositionConstraintBlock | None = None,
    ):
        """Initialize with a local name, wrapping it in a typed name."""
        super().__init__(location=location)
        object.__setattr__(
            self,
            "typed_name",
            LocalTypedNameReference(
                name_type=NameType.POSITION,
                name_content=local_name,
                location=SourceLocation.from_definition_name(
                    local_name, NameType.POSITION
                ),
            ),
        )
        object.__setattr__(self, "constraints", constraints)

    @property
    def constraint_typed_names(self) -> tuple[GlobalTypedNameReference, ...]:
        """Return the typed names of this position's constraint requirements, in source order."""
        if self.constraints is None:
            return ()
        return tuple(req.typed_global_name for req in self.constraints.requirements)


type AnyPositionDefinition = PositionDefinition | LocalPositionDefinition


@dataclass(frozen=True, slots=True)
class TypedName(ASTNode):
    """Represents a typed name (local or global)."""

    name_type: NameType
    name_content: NameContent
    _source_typed_name: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        """Compute and cache the source typed name string."""
        object.__setattr__(
            self,
            "_source_typed_name",
            sys.intern(f"{self.name_type.value}<{self.name_content.source_name}>"),
        )

    @property
    def source_typed_name(self) -> str:
        """Return typed-name text as it appears in the source."""
        return self._source_typed_name

    @property
    def full_typed_name(self) -> str:
        """Return canonical typed-name text including effective FQUN and path."""
        return self._source_typed_name


@dataclass(frozen=True, slots=True)
class GlobalTypedName(TypedName):
    """A typed global name, at either a definition site or a reference site."""

    name_content: GlobalNameContent


@dataclass(frozen=True, slots=True)
class GlobalTypedNameReference(GlobalTypedName):
    """Represents a typed global name reference."""

    name_content: ReferenceGlobalNameContent
    enclosing_fqun: Fqun
    _full_typed_name: str = field(init=False, repr=False, compare=False)

    @override
    def __post_init__(self):
        """Compute and cache the source and full typed-name strings."""
        super().__post_init__()
        fqun = self.name_content.fqun or self.enclosing_fqun
        object.__setattr__(
            self,
            "_full_typed_name",
            sys.intern(
                f"{self.name_type.value}<{fqun.canonical}:{self.name_content.path.name}>"
            ),
        )

    @property
    @override
    def full_typed_name(self) -> str:
        return self._full_typed_name


@dataclass(frozen=True, slots=True)
class LocalTypedNameReference(TypedName):
    """Represents a typed local name reference."""

    name_content: LocalNameContent


type TypedNameReference = GlobalTypedNameReference | LocalTypedNameReference


def chain_starts_with_global(key: tuple[str, ...]) -> bool:
    """Return whether the leftmost element of a chained-name key is a global."""
    return "/" in key[0]


@dataclass(frozen=True, slots=True)
class ChainedName(ASTNode):
    """A chain of typed name references joined by ::."""

    # TODO: We really need an ActionReference (a chain ending in an action) that
    # we use internally, paralleling PositionReference, even though it is not a
    # real AST object the parser produces. It would give the action-ending chains
    # we synthesize (e.g. with_suffix) the same static type safety that
    # PositionReference gives position-ending chains.
    typed_names: tuple[TypedNameReference, ...]
    # Filled lazily on first access by __getattr__ and cached in the slot.
    canonical_chained_name_tuple: tuple[str, ...] = field(
        init=False, repr=False, compare=False
    )
    canonical_chained_name: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        """Reject empty chains."""
        if not self.typed_names:
            raise ValueError("ChainedName must contain at least one typed name")

    # These are optimized because they were _the_ top hotspots in a CPU profile
    # of compilation when they were just computed always in __post_init__.
    #
    # Computed on first read and stored into the slot so later reads are a bare
    # slot read. The values are deterministic over the immutable typed_names, so
    # a benign race across threads recomputes an equal value and the slot store
    # is atomic. Anything other than these two names must raise so copy/pickle's
    # dunder probing still fails cleanly.
    def __getattr__(self, name: str) -> tuple[str, ...] | str:
        """Lazily compute and cache the canonical chained-name forms."""
        match name:
            case "canonical_chained_name_tuple":
                value = tuple(elem.full_typed_name for elem in self.typed_names)
            case "canonical_chained_name":
                value = "::".join(self.canonical_chained_name_tuple)
            case _:
                raise AttributeError(name)
        object.__setattr__(self, name, value)
        return value

    @property
    def source_chained_name(self) -> str:
        """Return chained name text as it appears in the source."""
        return "::".join(elem.source_typed_name for elem in self.typed_names)

    @property
    def starts_with_global(self) -> bool:
        """Return whether the chain's first element is a global reference."""
        return isinstance(self.typed_names[0], GlobalTypedNameReference)

    def get_last_action(self) -> GlobalTypedNameReference | None:
        """Return the last action element in the chain, or None."""
        for elem in reversed(self.typed_names):
            if elem.name_type == NameType.ACTION and isinstance(
                elem, GlobalTypedNameReference
            ):
                return elem
        return None

    def get_chain_to_last_action(self) -> ChainedName | None:
        """Return everything up to and including the last action element, or None."""
        for i in range(len(self.typed_names) - 1, -1, -1):
            if self.typed_names[i].name_type == NameType.ACTION:
                return ChainedName(
                    location=self.location,
                    typed_names=self.typed_names[: i + 1],
                )
        return None

    def get_last_action_children(self) -> PositionReference | None:
        """Return everything after the last action element, or None."""
        for i in range(len(self.typed_names) - 1, -1, -1):
            if self.typed_names[i].name_type == NameType.ACTION:
                tail = self.typed_names[i + 1 :]
                if not tail:
                    return None
                return PositionReference(
                    location=tail[0].location,
                    typed_names=tail,
                )
        return None

    def walk_parent_positions(self) -> Iterator[PositionReference]:
        """Yield parent position prefixes from root toward this position.

        For ``position<a>::action</x>::position</b>::position</c>``, yields
        references for ``position<a>`` and
        ``position<a>::action</x>::position</b>``, but not the full chain
        itself. Actions are skipped (bundled with the next position).
        """
        names = self.typed_names
        for i, elem in enumerate(names[:-1]):
            if elem.name_type != NameType.ACTION:
                yield PositionReference(
                    location=self.location,
                    typed_names=names[: i + 1],
                )

    def parent_position(self) -> PositionReference | None:
        """Return the nearest parent position, or None for single-element chains."""
        names = self.typed_names
        for i in range(len(names) - 2, -1, -1):
            if names[i].name_type != NameType.ACTION:
                return PositionReference(
                    location=self.location,
                    typed_names=names[: i + 1],
                )
        return None

    def source_form_in_universe(self, caller_fqun: Fqun) -> str:
        """Get the string form of the name as it would be written in source in the specified universe."""
        parts: list[str] = []
        for elem in self.typed_names:
            if isinstance(elem, GlobalTypedNameReference):
                effective_fqun = elem.name_content.fqun or elem.enclosing_fqun
                if effective_fqun.canonical != caller_fqun.canonical:
                    parts.append(elem.full_typed_name)
                    continue
            parts.append(elem.source_typed_name)
        return "::".join(parts)

    def with_prefix(self, prefix: ChainedName) -> Self:
        """Return a copy of ``self`` with ``prefix.typed_names`` prepended.

        The result has the same subclass as ``self`` (e.g. a
        ``PositionReference`` stays a ``PositionReference``).
        """
        return type(self)(
            location=self.location,
            typed_names=(*prefix.typed_names, *self.typed_names),
        )

    # TODO: There are likely other places in the codebase (including tests) that
    # still construct a ChainedName/PositionReference by spreading
    # ``(*chain.typed_names, ...)`` into the constructor; they should all use
    # with_suffix / with_position_suffix instead.
    def with_suffix(self, *names: TypedNameReference) -> ChainedName:
        """Return a ChainedName extending this chain with ``names`` appended.

        The result is a plain ChainedName regardless of what is appended; use
        with_position_suffix when the chain ends in a position and a
        PositionReference is wanted.
        """
        return ChainedName(
            location=self.location,
            typed_names=(*self.typed_names, *names),
        )

    def with_position_suffix(self, *names: TypedNameReference) -> PositionReference:
        """Return a PositionReference extending this chain with ``names`` appended.

        The appended chain must end in a position; the PositionReference
        constructor enforces that.
        """
        return PositionReference(
            location=self.location,
            typed_names=(*self.typed_names, *names),
        )

    def in_caller(self, caller_chain: ChainedName) -> Self:
        """Get the chained name of a contracted position from the perspective of the caller."""
        caller_ends_with_action = (
            caller_chain.typed_names[-1].name_type == NameType.ACTION
        )
        if self.starts_with_global and caller_ends_with_action:
            parent = caller_chain.parent_position()
            if parent is None:
                return self
            return self.with_prefix(parent)
        return self.with_prefix(caller_chain)

    def replace_parent_position_with_prefix(self, new_prefix: ChainedName) -> Self:
        """Return a new chain with everything up to and including the parent_position replaced with the new prefix."""
        parent = self.parent_position()
        if parent is None:
            raise ValueError(
                f"cannot replace parent prefix on a single-element chain: {self.source_chained_name}"
            )
        return type(self)(
            location=self.location,
            typed_names=(
                *new_prefix.typed_names,
                *self.typed_names[len(parent.typed_names) :],
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PositionReference(ChainedName):
    """Represents a position reference, possibly chained with ::."""

    def __init__(
        self,
        *,
        typed_names: tuple[TypedNameReference, ...],
        location: SourceLocation,
        from_source: bool = False,
    ):
        """Initialize, optionally validating that the chain ends with a position."""
        super().__init__(typed_names=typed_names, location=location)
        if not from_source and typed_names[-1].name_type != NameType.POSITION:
            raise ValueError(
                f"Last element of a PositionReference must be a position: {self.source_chained_name}"
            )


@dataclass(frozen=True, slots=True)
class ParticleStatement(ASTNode):
    """Base class for statements that operate on a target particle position."""

    target_position: PositionReference


@dataclass(frozen=True, slots=True)
class CreateParticleStatement(ParticleStatement):
    """Represents a 'create a particle in' statement."""


@dataclass(frozen=True, slots=True)
class MoveParticleStatement(ParticleStatement):
    """Represents a 'move the particle in ... to' statement."""

    source_position: PositionReference


@dataclass(frozen=True, slots=True)
class DestroyParticleStatement(ParticleStatement):
    """Represents a 'destroy the particle in' statement."""


type ActionStatement = (
    LocalPositionDefinition
    | CreateParticleStatement
    | MoveParticleStatement
    | DestroyParticleStatement
)


@dataclass(frozen=True, slots=True)
class PositionRequirementStatement(ASTNode):
    """Represents a position requirement statement in a constraints block."""

    typed_global_name: GlobalTypedNameReference


@dataclass(frozen=True, slots=True)
class QualityImplicationStatement(ASTNode):
    """Represents a quality implication statement."""

    typed_global_name: GlobalTypedNameReference


@dataclass(frozen=True, slots=True)
class PositionConstraintBlock(ASTNode):
    """Represents a position constraint block."""

    requirements: tuple[PositionRequirementStatement, ...]


@dataclass(frozen=True, slots=True)
class GlobalPathName(ASTNode):
    """Represents the path portion of a global name."""

    name: str

    def __post_init__(self):
        """Intern the path string to deduplicate across many references."""
        # str() coerces lark Token (a str subclass) to plain str; sys.intern rejects subclasses.
        object.__setattr__(self, "name", sys.intern(str(self.name)))

    @property
    def relative_path(self) -> define_path.DefinePath:
        """Return the path as a relative DefinePath."""
        return define_path.DefinePath(self.name[1:])

    def file_path(
        self,
        root: define_path.DefinePath = define_path.EMPTY,
    ) -> define_path.DefinePath:
        """Return the .dfn file path, prefixed by root."""
        return root / self.relative_path.with_suffix(constants.DEFINE_FILE_SUFFIX)


@dataclass(frozen=True, slots=True)
class PositionPresenceStatement(ASTNode):
    """Represents a position presence statement."""

    typed_name: LocalTypedNameReference
    position_reference: PositionReference = field(init=False)

    def __post_init__(self):
        """Pre-compute the position_reference from the typed name."""
        object.__setattr__(
            self,
            "position_reference",
            PositionReference(
                typed_names=(self.typed_name,),
                location=self.typed_name.location,
                from_source=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class DestructorConditionStatement(ASTNode):
    """Represents a destructor condition statement."""


type TriggerConditionStatement = (
    PositionPresenceStatement | DestructorConditionStatement
)


@dataclass(frozen=True, slots=True)
class TriggerConditionsBlock(ASTNode):
    """Represents a trigger conditions block."""

    conditions: tuple[TriggerConditionStatement, ...]


@dataclass(frozen=True, slots=True)
class ActionStatementsBlock(ASTNode):
    """Represents an action statements block."""

    statements: tuple[ActionStatement, ...]


@dataclass(frozen=True, slots=True)
class PositionInitBlock(ActionStatementsBlock):
    """Represents a position init block."""


@dataclass(frozen=True, slots=True, init=False)
class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

    interface_positions: tuple[LocalPositionDefinition, ...]
    trigger_conditions: TriggerConditionsBlock
    action_statements: ActionStatementsBlock

    # Computed properties
    interface_positions_by_name: dict[str, LocalPositionDefinition]
    interface_position_constraints: dict[str, frozenset[str]]
    trigger_position: LocalPositionDefinition | None

    def __init__(
        self,
        *,
        name: DefinitionGlobalNameContent,
        location: SourceLocation,
        quality_implications: tuple[QualityImplicationStatement, ...],
        interface_positions: tuple[LocalPositionDefinition, ...],
        trigger_conditions: TriggerConditionsBlock,
        action_statements: ActionStatementsBlock,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.ACTION,
                name_content=name,
                location=SourceLocation.from_definition_name(name, NameType.ACTION),
            ),
            quality_implications=quality_implications,
            location=location,
        )
        object.__setattr__(self, "interface_positions", interface_positions)
        object.__setattr__(self, "trigger_conditions", trigger_conditions)
        object.__setattr__(self, "action_statements", action_statements)
        # Instead of making these into properties, we compute them up front for two
        # reasons: (1) it's complex to make cached properties on frozen dataclasses
        # (2) this guarantees later thread-safety for accessing this information
        # on this object (instead of trying to potentially create multiple cached
        # copies of it across threads).
        object.__setattr__(
            self,
            "interface_positions_by_name",
            self._compute_interface_positions_by_name(),
        )
        object.__setattr__(
            self,
            "interface_position_constraints",
            self._compute_interface_position_constraints(),
        )
        object.__setattr__(self, "trigger_position", self._compute_trigger_position())

    @property
    def interface_position_names(self) -> tuple[TypedName, ...]:
        """Return the TypedName objects for all interface positions."""
        return tuple(pos.typed_name for pos in self.interface_positions)

    def _compute_interface_positions_by_name(
        self,
    ) -> dict[str, LocalPositionDefinition]:
        result: dict[str, LocalPositionDefinition] = {}
        for local_def in self.interface_positions:
            local_name = local_def.typed_name.source_typed_name
            if local_name not in result:
                result[local_name] = local_def
        return result

    def _compute_interface_position_constraints(self) -> dict[str, frozenset[str]]:
        result: dict[str, frozenset[str]] = {}
        for local_name, local_def in self.interface_positions_by_name.items():
            if local_def.constraints is None:
                result[local_name] = frozenset()
                continue
            result[local_name] = frozenset(
                requirement.typed_global_name.full_typed_name
                for requirement in local_def.constraints.requirements
            )
        return result

    def _compute_trigger_position(self) -> LocalPositionDefinition | None:
        first_condition = self.trigger_conditions.conditions[0]
        if not isinstance(first_condition, PositionPresenceStatement):
            return None
        trigger_name = first_condition.typed_name.source_typed_name
        return self.interface_positions_by_name.get(trigger_name)

    @property
    def trigger_position_reference(self) -> PositionReference | None:
        """Return the trigger condition's PositionReference, if valid."""
        first_condition = self.trigger_conditions.conditions[0]
        if self.trigger_position is None or not isinstance(
            first_condition, PositionPresenceStatement
        ):
            return None
        return first_condition.position_reference

    @property
    def is_destructor(self) -> bool:
        """Whether this action triggers when its particle is destroyed."""
        return isinstance(
            self.trigger_conditions.conditions[0], DestructorConditionStatement
        )


@dataclass(frozen=True, slots=True)
class Multiverse(ASTNode):
    """Represents a multiverse name."""

    name: str

    def __post_init__(self):
        """Intern the multiverse name to deduplicate across many references."""
        object.__setattr__(self, "name", sys.intern(str(self.name)))


@dataclass(frozen=True, slots=True)
class Universe(ASTNode):
    """Represents a universe name."""

    name: str

    def __post_init__(self):
        """Intern the universe name to deduplicate across many references."""
        object.__setattr__(self, "name", sys.intern(str(self.name)))


@dataclass(frozen=True, slots=True)
class Authority(ASTNode):
    """Represents an authority (domain plus optional path)."""

    name: str

    def __post_init__(self):
        """Intern the authority name to deduplicate across many references."""
        object.__setattr__(self, "name", sys.intern(str(self.name)))


@dataclass(frozen=True, slots=True)
class Fqun(ASTNode):
    """Represents a fully-qualified universe name."""

    multiverse: Multiverse | None
    authority: Authority | None
    universe: Universe
    canonical: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        """Compute and intern the canonical FQUN string."""
        # Pre-built because canonical is the only part of Fqun that
        # anything needs after name validation.
        if self.authority is None:
            value = self.universe.name
        else:
            parts: list[str] = []
            if self.multiverse is not None:
                parts.append(self.multiverse.name)
            parts.append(self.authority.name)
            parts.append(self.universe.name)
            value = ":".join(parts)
        # Interned to deduplicate across the many Fqun instances
        # sharing the same combination.
        object.__setattr__(self, "canonical", sys.intern(value))


@dataclass(frozen=True, slots=True)
class GlobalNameContent(NameContent):
    """Base class for global name-like nodes."""

    fqun: Fqun | None
    path: GlobalPathName

    @property
    @override
    def source_name(self) -> str:
        if self.fqun is not None:
            return f"{self.fqun.canonical}:{self.path.name}"
        return self.path.name


@dataclass(frozen=True, slots=True)
class DefinitionGlobalNameContent(GlobalNameContent):
    """Represents a global name at a definition site."""

    fqun: Fqun


@dataclass(frozen=True, slots=True)
class ReferenceGlobalNameContent(GlobalNameContent):
    """Represents a global name at a reference site."""


@dataclass(frozen=True, slots=True)
class GlobalTypedNameInDefinition(GlobalTypedName):
    """Represents a typed global name at a definition site."""

    name_content: DefinitionGlobalNameContent
