"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Self, override

from define.compiler import constants

if TYPE_CHECKING:
    from define.compiler.lark import lark_standalone


class NameType(enum.StrEnum):
    """The type of a quality definition."""

    POSITION = "position"
    ACTION = "action"


# TODO: Should include file name.
@dataclass
class SourcePosition:
    """Represents a position in source code."""

    line: int
    column: int
    end_line: int
    end_column: int

    @classmethod
    def from_meta(cls, meta: lark_standalone.Meta) -> Self:
        """Create a SourcePosition from a Lark Meta object."""
        return cls(
            line=meta.line,
            column=meta.column,
            end_line=meta.end_line,
            end_column=meta.end_column,
        )

    @classmethod
    def from_token(cls, token: lark_standalone.Token) -> Self:
        """Create a SourcePosition from a Lark Token."""
        if (
            token.line is None
            or token.column is None
            or token.end_line is None
            or token.end_column is None
        ):
            raise ValueError(f"Token {token} is missing position information")
        return cls(
            line=token.line,
            column=token.column,
            end_line=token.end_line,
            end_column=token.end_column,
        )


@dataclass
class ASTNode:
    """Base class for all AST nodes."""

    position: SourcePosition


@dataclass
class Program(ASTNode):
    """Represents the entire program."""

    definitions: list[QualityDefinition]


@dataclass
class QualityDefinition(ASTNode):
    """Base class for quality definitions (positions and actions)."""

    typed_name: GlobalTypedNameInDefinition


@dataclass(init=False)
class PositionDefinition(QualityDefinition):
    """Represents a position definition."""

    constraints: PositionConstraintBlock | None

    def __init__(
        self,
        *,
        name: DefinitionGlobalNameContent,
        position: SourcePosition,
        constraints: PositionConstraintBlock | None = None,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.POSITION,
                name_content=name,
                position=name.position,
            ),
            position=position,
        )
        self.constraints = constraints


@dataclass
class NameContent(ASTNode, abc.ABC):
    """Base class for name content nodes (local or global)."""

    @abc.abstractmethod
    def full_name(self, in_universe: Fqun | None = None) -> str:
        """Return the full name text, optionally resolved against a universe."""


@dataclass
class LocalNameContent(NameContent):
    """Represents a local name."""

    name: str

    @override
    def full_name(self, in_universe: Fqun | None = None) -> str:
        """Return the local name."""
        return self.name


@dataclass(init=False)
class LocalPositionDefinition(ASTNode):
    """Represents a local position definition within an action block."""

    typed_name: LocalTypedNameReference
    constraints: PositionConstraintBlock | None

    def __init__(
        self,
        *,
        local_name: LocalNameContent,
        position: SourcePosition,
        constraints: PositionConstraintBlock | None = None,
    ):
        """Initialize with a local name, wrapping it in a typed name."""
        super().__init__(position=position)
        self.typed_name = LocalTypedNameReference(
            name_type=NameType.POSITION,
            name_content=local_name,
            position=local_name.position,
        )
        self.constraints = constraints


@dataclass
class TypedName(ASTNode):
    """Represents a typed name (local or global)."""

    name_type: NameType
    name_content: NameContent

    def full_typed_name(self, in_universe: Fqun | None = None) -> str:
        """Return canonical typed-name text including effective FQUN and path."""
        return f"{self.name_type.value}<{self.name_content.full_name(in_universe=in_universe)}>"


@dataclass
class GlobalTypedNameReference(TypedName):
    """Represents a typed global name reference."""

    name_content: ReferenceGlobalNameContent  # pyright: ignore[reportIncompatibleVariableOverride]


@dataclass
class LocalTypedNameReference(TypedName):
    """Represents a typed local name reference."""

    name_content: LocalNameContent  # pyright: ignore[reportIncompatibleVariableOverride]


@dataclass
class PositionReference(ASTNode):
    """Represents a position reference, possibly chained with ::."""

    chain: list[TypedName]


@dataclass
class CreateDimensionPointStatement(ASTNode):
    """Represents a 'create a dimension point in' statement."""

    position_reference: PositionReference


@dataclass
class MoveDimensionPointStatement(ASTNode):
    """Represents a 'move the dimension point in ... to' statement."""

    from_position: PositionReference
    to_position: PositionReference


type ActionStatement = (
    LocalPositionDefinition
    | CreateDimensionPointStatement
    | MoveDimensionPointStatement
)


@dataclass
class PositionRequirementStatement(ASTNode):
    """Represents a position requirement statement in a constraints block."""

    typed_global_name: GlobalTypedNameReference


@dataclass
class PositionConstraintBlock(ASTNode):
    """Represents a position constraint block."""

    requirements: list[PositionRequirementStatement]


@dataclass
class GlobalPathName(ASTNode):
    """Represents the path portion of a global name."""

    name: str

    @property
    def relative_path(self) -> PurePosixPath:
        """Return the path as a relative POSIX path object."""
        return PurePosixPath(self.name[1:])

    def file_path(self, root: PurePosixPath = constants.PROJECT_ROOT) -> PurePosixPath:
        """Return the .def file path, prefixed by root."""
        return root / self.relative_path.with_suffix(".def")


@dataclass
class TriggerConditionsBlock(ASTNode):
    """Represents a trigger conditions block."""


@dataclass
class ActionStatementsBlock(ASTNode):
    """Represents an action statements block."""

    statements: list[ActionStatement]


@dataclass
class ActionDefinitionBlock(ASTNode):
    """Represents an action definition block."""

    local_definitions: list[LocalPositionDefinition]
    trigger_conditions: TriggerConditionsBlock
    action_statements: ActionStatementsBlock


@dataclass(init=False)
class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

    definition_block: ActionDefinitionBlock | None

    def __init__(
        self,
        *,
        name: DefinitionGlobalNameContent,
        position: SourcePosition,
        definition_block: ActionDefinitionBlock | None = None,
    ):
        """Initialize with a global name, wrapping it in a typed definition name."""
        super().__init__(
            typed_name=GlobalTypedNameInDefinition(
                name_type=NameType.ACTION,
                name_content=name,
                position=name.position,
            ),
            position=position,
        )
        self.definition_block = definition_block


@dataclass
class Multiverse(ASTNode):
    """Represents a multiverse name."""

    name: str


@dataclass
class Universe(ASTNode):
    """Represents a universe name."""

    name: str


@dataclass
class Authority(ASTNode):
    """Represents an authority (domain plus optional path)."""

    name: str


@dataclass
class Fqun(ASTNode):
    """Represents a fully-qualified universe name."""

    multiverse: Multiverse | None
    authority: Authority | None
    universe: Universe

    @property
    def canonical(self) -> str:
        """Return the canonical FQUN string."""
        if self.authority is None:
            return self.universe.name

        authority_str = self.authority.name

        parts: list[str] = []
        if self.multiverse is not None:
            parts.append(self.multiverse.name)
        parts.append(authority_str)
        parts.append(self.universe.name)
        return ":".join(parts)


@dataclass
class GlobalNameContent(NameContent):
    """Base class for global name-like nodes."""

    fqun: Fqun | None
    path: GlobalPathName

    @override
    def full_name(self, in_universe: Fqun | None = None) -> str:
        """Return canonical FQUN:path text, resolved against a universe if needed."""
        fqun = self.fqun or in_universe
        if fqun is None:
            raise ValueError("global name requires an effective FQUN")
        return f"{fqun.canonical}:{self.path.name}"


@dataclass
class DefinitionGlobalNameContent(GlobalNameContent):
    """Represents a global name at a definition site."""

    fqun: Fqun  # pyright: ignore[reportIncompatibleVariableOverride]


@dataclass
class ReferenceGlobalNameContent(GlobalNameContent):
    """Represents a global name at a reference site."""


@dataclass
class GlobalTypedNameInDefinition(TypedName):
    """Represents a typed global name at a definition site."""

    name_content: DefinitionGlobalNameContent  # pyright: ignore[reportIncompatibleVariableOverride]
