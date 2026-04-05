"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

import abc
import enum
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Self, override

from define.compiler import constants

if TYPE_CHECKING:
    from collections.abc import Iterator

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

    @classmethod
    def from_meta(
        cls, meta: lark_standalone.Meta, file_path: PurePosixPath | None = None
    ) -> Self:
        """Create a SourceLocation from a Lark Meta object."""
        return cls(
            line=meta.line,
            column=meta.column,
            end_line=meta.end_line,
            end_column=meta.end_column,
            file_path=file_path,
        )

    @classmethod
    def from_token(
        cls, token: lark_standalone.Token, file_path: PurePosixPath | None = None
    ) -> Self:
        """Create a SourceLocation from a Lark Token."""
        if (
            token.line is None
            or token.column is None
            or token.end_line is None
            or token.end_column is None
        ):
            raise ValueError(f"Token {token} is missing location information")
        return cls(
            line=token.line,
            column=token.column,
            end_line=token.end_line,
            end_column=token.end_column,
            file_path=file_path,
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

    definitions: list[QualityDefinition]


@dataclass(frozen=True, slots=True)
class QualityDefinition(ASTNode):
    """Base class for quality definitions (positions and actions)."""

    typed_name: GlobalTypedNameInDefinition


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
        constraints: PositionConstraintBlock | None = None,
        initialization: PositionInitBlock | None = None,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.POSITION,
                name_content=name,
                # TODO: This is the wrong location.
                location=name.location,
            ),
            location=location,
        )
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "initialization", initialization)

    @property
    def constraint_names(self) -> frozenset[str]:
        """Return the fully-qualified constraint names for this position."""
        if self.constraints is None:
            return frozenset()
        fqun = self.typed_name.name_content.fqun
        return frozenset(
            requirement.typed_global_name.full_typed_name(in_universe=fqun)
            for requirement in self.constraints.requirements
        )


@dataclass(frozen=True, slots=True)
class NameContent(ASTNode, abc.ABC):
    """Base class for name content nodes (local or global)."""

    @abc.abstractmethod
    def full_name(self, in_universe: Fqun) -> str:
        """Return the full name text, resolved against a universe."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Return the name as it appears in the source."""


@dataclass(frozen=True, slots=True)
class LocalNameContent(NameContent):
    """Represents a local name."""

    name: str

    @override
    def full_name(self, in_universe: Fqun) -> str:
        """Return the local name."""
        return self.name

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
                location=local_name.location,
            ),
        )
        object.__setattr__(self, "constraints", constraints)


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
            f"{self.name_type.value}<{self.name_content.source_name}>",
        )

    def full_typed_name(self, in_universe: Fqun) -> str:
        """Return canonical typed-name text including effective FQUN and path."""
        return f"{self.name_type.value}<{self.name_content.full_name(in_universe=in_universe)}>"

    @property
    def source_typed_name(self) -> str:
        """Return typed-name text as it appears in the source."""
        return self._source_typed_name


@dataclass(frozen=True, slots=True)
class GlobalTypedNameReference(TypedName):
    """Represents a typed global name reference."""

    name_content: ReferenceGlobalNameContent


@dataclass(frozen=True, slots=True)
class LocalTypedNameReference(TypedName):
    """Represents a typed local name reference."""

    name_content: LocalNameContent


type TypedNameReference = GlobalTypedNameReference | LocalTypedNameReference


@dataclass(frozen=True, slots=True)
class ChainedName(ASTNode):
    """A chain of typed name references joined by ::."""

    typed_names: list[TypedNameReference]

    def canonical_chained_name(self, in_universe: Fqun) -> str:
        """Return the canonical chained name string."""
        return "::".join(
            elem.full_typed_name(in_universe=in_universe) for elem in self.typed_names
        )

    def canonical_chained_name_tuple(self, in_universe: Fqun) -> tuple[str, ...]:
        """Return the canonical chained name as a tuple of typed-name strings."""
        return tuple(
            elem.full_typed_name(in_universe=in_universe) for elem in self.typed_names
        )

    @property
    def source_chained_name(self) -> str:
        """Return chained name text as it appears in the source."""
        return "::".join(elem.source_typed_name for elem in self.typed_names)

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


@dataclass(frozen=True, slots=True, init=False)
class PositionReference(ChainedName):
    """Represents a position reference, possibly chained with ::."""

    def __init__(
        self,
        *,
        typed_names: list[TypedNameReference],
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
class DimensionPointStatement(ASTNode):
    """Base class for statements that operate on a target dimension point position."""

    target_position: PositionReference


@dataclass(frozen=True, slots=True)
class CreateDimensionPointStatement(DimensionPointStatement):
    """Represents a 'create a dimension point in' statement."""


@dataclass(frozen=True, slots=True)
class MoveDimensionPointStatement(DimensionPointStatement):
    """Represents a 'move the dimension point in ... to' statement."""

    source_position: PositionReference


type ActionStatement = (
    LocalPositionDefinition
    | CreateDimensionPointStatement
    | MoveDimensionPointStatement
)


@dataclass(frozen=True, slots=True)
class PositionRequirementStatement(ASTNode):
    """Represents a position requirement statement in a constraints block."""

    typed_global_name: GlobalTypedNameReference


@dataclass(frozen=True, slots=True)
class PositionConstraintBlock(ASTNode):
    """Represents a position constraint block."""

    requirements: list[PositionRequirementStatement]


@dataclass(frozen=True, slots=True)
class GlobalPathName(ASTNode):
    """Represents the path portion of a global name."""

    name: str

    @property
    def relative_path(self) -> PurePosixPath:
        """Return the path as a relative POSIX path object."""
        return PurePosixPath(self.name[1:])

    def file_path(self, root: PurePosixPath = constants.PROJECT_ROOT) -> PurePosixPath:
        """Return the .dfn file path, prefixed by root."""
        return root / self.relative_path.with_suffix(".dfn")


@dataclass(frozen=True, slots=True)
class TriggerConditionStatement(ASTNode):
    """Represents a trigger condition statement."""

    typed_name: LocalTypedNameReference
    position_reference: PositionReference = field(init=False)

    def __post_init__(self):
        """Pre-compute the position_reference from the typed name."""
        object.__setattr__(
            self,
            "position_reference",
            PositionReference(
                typed_names=[self.typed_name],
                location=self.typed_name.location,
                from_source=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class TriggerConditionsBlock(ASTNode):
    """Represents a trigger conditions block."""

    conditions: list[TriggerConditionStatement]


@dataclass(frozen=True, slots=True)
class ActionStatementsBlock(ASTNode):
    """Represents an action statements block."""

    statements: list[ActionStatement]


@dataclass(frozen=True, slots=True)
class PositionInitBlock(ActionStatementsBlock):
    """Represents a position init block."""


@dataclass(frozen=True, slots=True)
class ActionDefinitionBlock(ASTNode):
    """Represents an action definition block."""

    interface_positions: list[LocalPositionDefinition]
    trigger_conditions: TriggerConditionsBlock
    action_statements: ActionStatementsBlock


# TODO: I think we should ban empty actions. I can't think of a use case for them.
@dataclass(frozen=True, slots=True, init=False)
class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

    definition_block: ActionDefinitionBlock | None

    # Computed properties
    interface_positions: dict[str, LocalPositionDefinition]
    interface_position_constraints: dict[str, frozenset[str]]
    trigger_position: LocalPositionDefinition | None

    def __init__(
        self,
        *,
        name: DefinitionGlobalNameContent,
        location: SourceLocation,
        definition_block: ActionDefinitionBlock | None = None,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.ACTION,
                name_content=name,
                # TODO: This is the wrong location.
                location=name.location,
            ),
            location=location,
        )
        object.__setattr__(self, "definition_block", definition_block)
        # Instead of making these into properties, we compute them up front for two
        # reasons: (1) it's complex to make cached properties on frozen dataclasses
        # (2) this guarantees later thread-safety for accessing this information
        # on this object (instead of trying to potentially create multiple cached
        # copies of it across threads).
        object.__setattr__(
            self,
            "interface_positions",
            self._compute_interface_positions(),
        )
        object.__setattr__(
            self,
            "interface_position_constraints",
            self._compute_interface_position_constraints(),
        )
        object.__setattr__(self, "trigger_position", self._compute_trigger_position())

    @property
    def interface_position_names(self) -> list[TypedName]:
        """Return the TypedName objects for all interface positions."""
        if self.definition_block is None:
            return []
        return [pos.typed_name for pos in self.definition_block.interface_positions]

    def _compute_interface_positions(self) -> dict[str, LocalPositionDefinition]:
        if self.definition_block is None:
            return {}
        result: dict[str, LocalPositionDefinition] = {}
        for local_def in self.definition_block.interface_positions:
            local_name = local_def.typed_name.source_typed_name
            if local_name not in result:
                result[local_name] = local_def
        return result

    def _compute_interface_position_constraints(self) -> dict[str, frozenset[str]]:
        if self.definition_block is None:
            return {}
        fqun = self.typed_name.name_content.fqun
        result: dict[str, frozenset[str]] = {}
        for local_name, local_def in self.interface_positions.items():
            if local_def.constraints is None:
                result[local_name] = frozenset()
                continue
            result[local_name] = frozenset(
                requirement.typed_global_name.full_typed_name(in_universe=fqun)
                for requirement in local_def.constraints.requirements
            )
        return result

    def _compute_trigger_position(self) -> LocalPositionDefinition | None:
        if self.definition_block is None:
            return None
        conditions = self.definition_block.trigger_conditions.conditions
        if not conditions:
            return None
        trigger_name = conditions[0].typed_name.source_typed_name
        return self.interface_positions.get(trigger_name)

    @property
    def trigger_position_reference(self) -> PositionReference | None:
        """Return the trigger condition's PositionReference, if valid."""
        if self.definition_block is None or self.trigger_position is None:
            return None
        return self.definition_block.trigger_conditions.conditions[0].position_reference


@dataclass(frozen=True, slots=True)
class Multiverse(ASTNode):
    """Represents a multiverse name."""

    name: str


@dataclass(frozen=True, slots=True)
class Universe(ASTNode):
    """Represents a universe name."""

    name: str


@dataclass(frozen=True, slots=True)
class Authority(ASTNode):
    """Represents an authority (domain plus optional path)."""

    name: str


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

    @override
    def full_name(self, in_universe: Fqun) -> str:
        """Return canonical FQUN:path text, resolved against a universe."""
        fqun = self.fqun or in_universe
        return f"{fqun.canonical}:{self.path.name}"

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
class GlobalTypedNameInDefinition(TypedName):
    """Represents a typed global name at a definition site."""

    name_content: DefinitionGlobalNameContent

    @override
    def full_typed_name(self, in_universe: Fqun) -> str:
        return self._source_typed_name
