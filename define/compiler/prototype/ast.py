"""Abstract Syntax Tree node definitions for the Define language."""

from dataclasses import dataclass, field
from functools import cached_property


class ASTError(Exception):
    """Base class for all AST errors."""


class StringLiteralError(ASTError):
    """Raised when a string literal is invalid."""


class NumberLiteralError(ASTError):
    """Raised when a number literal is invalid."""


class UniverseNotFoundError(ASTError):
    """Raised when a universe with the specified name is not found."""


@dataclass(kw_only=True)
class ASTNode:
    """Base class for all AST nodes."""


@dataclass
class Program(ASTNode):
    """Represents the entire program (collection of universe blocks)."""

    universes: list["UniverseBlock"]

    def _get_universe_by_name(self, name: str) -> "UniverseBlock":
        for universe in self.universes:
            if universe.name == name:
                return universe
        available = ", ".join(str(u.name) for u in self.universes) or "none"
        raise UniverseNotFoundError(
            f"Universe {name!r} not found. Available universes: {available}"
        )

    def get_abstract_universe(self) -> "UniverseBlock":
        """Get the AbstractUniverse block.

        Raises:
            UniverseNotFoundError: If no AbstractUniverse block exists
        """
        return self._get_universe_by_name("AbstractUniverse")

    def get_physical_universe(self) -> "UniverseBlock":
        """Get the PhysicalUniverse block.

        Raises:
            UniverseNotFoundError: If no PhysicalUniverse block exists
        """
        return self._get_universe_by_name("PhysicalUniverse")


@dataclass
class UniverseBlock(ASTNode):
    """Represents a universe block (e.g., AbstractUniverse:, PhysicalUniverse:)."""

    name: str
    statements: list[ASTNode]

    def get_statements_by_type[T: ASTNode](self, stmt_type: type[T]) -> list[T]:
        """Find statements of a specific type in this universe block.

        Args:
            stmt_type: The type of statement to find (e.g., TypeDeclaration, EntityCreation)

        Returns:
            A list of statements that are instances of the specified type,
            or an empty list if no statements of the specified type are found.
        """
        return [stmt for stmt in self.statements if isinstance(stmt, stmt_type)]


@dataclass
class BaseTypeDeclaration(ASTNode):
    """Base class for type declarations."""

    type_name: str


@dataclass
class CompilerTypeDeclaration(BaseTypeDeclaration):
    """Represents a compiler type declaration (e.g., Number is.)."""


@dataclass
class TypeDeclaration(BaseTypeDeclaration):
    """Represents a type declaration with a parent type (e.g., Source is a ViewPoint)."""

    parent_type: str


@dataclass
class PropertyDeclaration(ASTNode):
    """Represents a property declaration (e.g., String has a String named value)."""

    type_name: str
    property_type: str
    property_name: str


@dataclass
class ValueReference(ASTNode):
    """Base class for values that can be assigned to a property or passed to an action.

    This can be a string literal, number, or property/entity reference.
    """


@dataclass
class StringLiteral(ValueReference):
    """Represents a string literal value."""

    raw_value: str

    @cached_property
    def value(self) -> str:
        """Parse the raw string value by removing quotes and unescaping."""
        if not (self.raw_value.startswith('"') and self.raw_value.endswith('"')):
            raise StringLiteralError(f"Invalid string literal: '{self.raw_value}'")
        # TODO: Better string literal parsing
        return self.raw_value[1:-1].replace('\\"', '"').replace("\\\\", "\\")


@dataclass
class NumberLiteral(ValueReference):
    """Represents a numeric literal value (integer or floating-point)."""

    raw_value: str

    @cached_property
    def value(self) -> float | int:
        """Parse the raw number value to int or float."""
        try:
            if "." in self.raw_value:
                return float(self.raw_value)
            return int(self.raw_value)
        except ValueError as e:
            raise NumberLiteralError(
                f"Invalid number literal: '{self.raw_value}'"
            ) from e


@dataclass
class PropertyOrEntityReference(ValueReference):
    """Represents a reference to a property or entity (e.g., Owner's propertyName)."""

    owner: str
    property_name: str


@dataclass
class EntityCreation(ASTNode):
    """Represents an entity creation (e.g., Source creates a String named helloWorld:)."""

    creator: str
    type_name: str
    entity_name: str
    properties: list["PropertyAssignment"]


@dataclass
class PropertyAssignment(ASTNode):
    """Represents a property assignment (e.g., value: "Hello, world!")."""

    name: str
    value: ValueReference


@dataclass
class KnowledgeStatement(ASTNode):
    """Represents a knowledge statement (e.g., Machine knows Source's helloWorld)."""

    knower: str
    owner: str
    entity_name: str


@dataclass
class ActionParameter(ASTNode):
    """Represents an action parameter (e.g., a String named str)."""

    param_type: str
    param_name: str


@dataclass
class ActionDeclaration(ASTNode):
    """Represents an action declaration (e.g., Terminal can Output using a String named str:)."""

    type_name: str
    action_name: str
    parameters: list[ActionParameter]
    body: list["ActionExecution"] = field(default_factory=list)


@dataclass
class ActionExecution(ASTNode):
    """Represents an action execution (e.g., Machine makes terminal Output helloWorld.)."""

    actor: str
    target: PropertyOrEntityReference
    action_name: str
    arguments: list[ValueReference]
