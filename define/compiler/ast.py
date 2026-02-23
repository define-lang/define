"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Self

from define.compiler import constants

if typing.TYPE_CHECKING:
    import lark


class TypeName(enum.StrEnum):
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
    def from_meta(cls, meta: lark.tree.Meta) -> Self:
        """Create a SourcePosition from a Lark Meta object."""
        return cls(
            line=meta.line,
            column=meta.column,
            end_line=meta.end_line,
            end_column=meta.end_column,
        )

    @classmethod
    def from_token(cls, token: lark.Token) -> Self:
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

    name: GlobalNameDefinition
    type_name: TypeName

    @property
    def fully_qualified_typed_name(self) -> str:
        """Return canonical typed-name text including FQUN and path."""
        return f"{self.type_name.value}<{self.name.fully_qualified()}>"


@dataclass
class PositionDefinition(QualityDefinition):
    """Represents a position definition."""

    type_name: TypeName = TypeName.POSITION
    constraints: PositionConstraintBlock | None = None


@dataclass
class LocalName(ASTNode):
    """Represents a local name."""

    name: str


@dataclass
class LocalPositionDefinition(ASTNode):
    """Represents a local position definition within an action block."""

    local_name: LocalName
    constraints: PositionConstraintBlock | None = None


type ActionStatement = LocalPositionDefinition


@dataclass
class TypedGlobalNameReference(ASTNode):
    """Represents a typed global name reference."""

    type_name: TypeName
    global_name: GlobalNameReference

    def fully_qualified_typed_name(self, with_fqun: Fqun | None = None) -> str:
        """Return canonical typed-name text including effective FQUN and path."""
        return (
            f"{self.type_name.value}"
            + f"<{self.global_name.fully_qualified(with_fqun=with_fqun)}>"
        )


@dataclass
class PositionRequirementStatement(ASTNode):
    """Represents a position requirement statement in a constraints block."""

    typed_global_name: TypedGlobalNameReference


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


@dataclass
class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

    type_name: TypeName = TypeName.ACTION
    definition_block: ActionDefinitionBlock | None = None


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
class GlobalName(ASTNode):
    """Base class for global name-like nodes."""

    fqun: Fqun | None
    path: GlobalPathName

    def fully_qualified(self, with_fqun: Fqun | None = None) -> str:
        """Return canonical FQUN:path text with optional short-form resolution."""
        if with_fqun is not None and self.fqun is not None:
            raise ValueError(
                "global name already has an FQUN; with_fqun is not allowed"
            )
        fqun = self.fqun or with_fqun
        if fqun is None:
            raise ValueError("global name requires an effective FQUN")
        return f"{fqun.canonical}:{self.path.name}"


@dataclass
class GlobalNameDefinition(GlobalName):
    """Represents a global name at a definition site."""

    fqun: Fqun  # pyright: ignore[reportIncompatibleVariableOverride]


@dataclass
class GlobalNameReference(GlobalName):
    """Represents a global name at a reference site."""
