"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import lark  # noqa: TC002


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

    name: GlobalName


@dataclass
class PositionDefinition(QualityDefinition):
    """Represents a position definition."""


@dataclass
class LocalName(ASTNode):
    """Represents a local name."""

    name: str


@dataclass
class LocalPositionDefinition(ASTNode):
    """Represents a local position definition within an action block."""

    local_name: LocalName


@dataclass
class GlobalPathNameSegment(ASTNode):
    """Represents a single segment of a global name path."""

    name: str


@dataclass
class GlobalPathName(ASTNode):
    """Represents the path portion of a global name."""

    segments: list[GlobalPathNameSegment]

    @property
    def relative_path(self) -> Path:
        """Return the path as a relative Path object."""
        return Path(*[s.name for s in self.segments])

    @property
    def path_string(self) -> str:
        """Return the full path as a '/' prefixed string (e.g. '/foo/bar')."""
        return "/" + str(self.relative_path)


@dataclass
class TriggerConditionsBlock(ASTNode):
    """Represents a trigger conditions block."""


@dataclass
class ActionStatementsBlock(ASTNode):
    """Represents an action statements block."""


@dataclass
class ActionDefinitionBlock(ASTNode):
    """Represents an action definition block."""

    local_definitions: list[LocalPositionDefinition]
    trigger_conditions: TriggerConditionsBlock
    action_statements: ActionStatementsBlock


@dataclass
class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

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

    domain: str
    path: list[str] = field(default_factory=list)


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

        authority_str = self.authority.domain
        if self.authority.path:
            authority_str += "/" + "/".join(self.authority.path)

        parts: list[str] = []
        if self.multiverse is not None:
            parts.append(self.multiverse.name)
        parts.append(authority_str)
        parts.append(self.universe.name)
        return ":".join(parts)


@dataclass
class GlobalName(ASTNode):
    """Represents a fully-qualified global name."""

    fqun: Fqun
    path: GlobalPathName
