"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ASTNode:
    """Base class for all AST nodes."""


@dataclass
class Program(ASTNode):
    """Represents the entire program."""

    definitions: list[PositionDefinition]


@dataclass
class PositionDefinition(ASTNode):
    """Represents a position definition."""

    name: GlobalName


@dataclass
class Authority(ASTNode):
    """Represents an authority (domain plus optional path)."""

    domain: str
    path: list[str] = field(default_factory=list)


@dataclass
class Fqun(ASTNode):
    """Represents a fully-qualified universe name."""

    multiverse: str | None
    authority: Authority | None
    universe: str


@dataclass
class GlobalName(ASTNode):
    """Represents a fully-qualified global name."""

    fqun: Fqun
    path: list[str]
