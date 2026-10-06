"""Abstract Syntax Tree node definitions for the Define language."""

from __future__ import annotations

import abc
import sys
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    Generic,
    Self,
    TypeVar,
    cast,
    override,
)

import msgspec

from define.compiler import chained_name, constants, name_types
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    import lark_cython


class ASTNodeMeta(msgspec.StructMeta, abc.ABCMeta):
    """Combine msgspec struct construction with abstract AST base classes."""


class SourceLocation(msgspec.Struct, frozen=True):
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
        start: ASTNode | lark_cython.Token,
        end: ASTNode | lark_cython.Token,
        file_path: PurePosixPath | None = None,
        end_column_offset: int = 0,
    ) -> Self:
        """Build a SourceLocation spanning ``start`` through ``end``.

        Each argument is either an ``ASTNode`` (whose ``.location`` is read)
        or a ``lark_cython.Token`` (whose lexer-set
        ``line``/``column``/``end_line``/``end_column`` are read). When
        ``start`` and ``end`` are the same instance, the result is that
        item's full span.
        """
        if isinstance(start, ASTNode):
            start_line = start.location.line
            start_column = start.location.column
        else:
            if start.line < 0 or start.column < 0:
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
        cls, name_content: NameContent, name_type: name_types.NameType
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


class ASTNode(msgspec.Struct, metaclass=ASTNodeMeta, eq=False):
    """Base class for all AST nodes.

    Treat nodes as immutable after construction so cached values remain valid.
    """

    location: SourceLocation


class Program(ASTNode):
    """Represents the entire program."""

    definitions: tuple[GlobalDefinition, ...]


class GlobalDefinition(ASTNode):
    """Base class for definitions in the global context."""

    typed_name: GlobalTypedNameInDefinition


class QualityDefinition(GlobalDefinition):
    """Base class for quality definitions."""

    quality_implications: tuple[QualityImplicationStatement, ...]


class EncodingDefinition(GlobalDefinition):
    """Represents an encoding definition."""

    @classmethod
    def from_name(
        cls, *, name: DefinitionGlobalNameContent, location: SourceLocation
    ) -> Self:
        """Initialize with a global name."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=name_types.NameType.ENCODING,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, name_types.NameType.ENCODING
                ),
            ),
            location=location,
        )


class PotentialLiteralDefinition(GlobalDefinition):
    """Represents a potential literal definition."""

    encoding: GlobalTypedNameReference

    @classmethod
    def from_name(
        cls,
        *,
        name: DefinitionGlobalNameContent,
        encoding: GlobalTypedNameReference,
        location: SourceLocation,
    ) -> Self:
        """Initialize with a global name and its encoding."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=name_types.NameType.LITERAL,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, name_types.NameType.LITERAL
                ),
            ),
            encoding=encoding,
            location=location,
        )


class OperationDefinition(GlobalDefinition):
    """Base class for Value Operation and Encoding Operation definitions."""

    definition_name_type: ClassVar[name_types.NameType]

    views: tuple[ViewDefinition, ...]
    operation_statements: tuple[OperationStatement, ...]

    @classmethod
    def from_name(
        cls,
        *,
        name: DefinitionGlobalNameContent,
        views: tuple[ViewDefinition, ...],
        operation_statements: tuple[OperationStatement, ...],
        location: SourceLocation,
    ) -> Self:
        """Initialize with a global name, its views, and its statements."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=cls.definition_name_type,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, cls.definition_name_type
                ),
            ),
            views=views,
            operation_statements=operation_statements,
            location=location,
        )

    def view_index(self, view_name: str) -> int | None:
        """Return the index of the first view with this name, if there is one."""
        # Operations have only a few views, so scanning them is as fast as a
        # dict lookup, and it avoids storing a dict on every operation
        # definition for the whole compile.
        for index, view in enumerate(self.views):
            if view.typed_name.source_typed_name == view_name:
                return index
        return None

    def get_view(self, view_name: str) -> ViewDefinition | None:
        """Return the first view with this name, if there is one."""
        # This scans the views instead of keeping a dict of them for the same
        # reason view_index does.
        index = self.view_index(view_name)
        if index is None:
            return None
        return self.views[index]


class ValueOperationDefinition(OperationDefinition):
    """Represents a Value Operation definition."""

    definition_name_type: ClassVar[name_types.NameType] = name_types.NameType.OPERATION


class EncodingOperationDefinition(OperationDefinition):
    """Represents an Encoding Operation definition."""

    definition_name_type: ClassVar[name_types.NameType] = (
        name_types.NameType.ENCODING_OPERATION
    )


class ValueDefinition(QualityDefinition):
    """Represents a value type definition."""

    @classmethod
    def from_name(
        cls, *, name: DefinitionGlobalNameContent, location: SourceLocation
    ) -> Self:
        """Initialize with a global name."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=name_types.NameType.VALUE,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, name_types.NameType.VALUE
                ),
            ),
            quality_implications=(),
            location=location,
        )


class PositionDefinition(QualityDefinition):
    """Represents a position definition."""

    constraints: PositionConstraintBlock | None = None

    @classmethod
    def from_name(
        cls,
        *,
        name: DefinitionGlobalNameContent,
        location: SourceLocation,
        quality_implications: tuple[QualityImplicationStatement, ...] = (),
        constraints: PositionConstraintBlock | None = None,
    ) -> Self:
        """Initialize with a global name, wrapping it in a typed definition name."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=name_types.NameType.POSITION,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, name_types.NameType.POSITION
                ),
            ),
            quality_implications=quality_implications,
            location=location,
            constraints=constraints,
        )

    @property
    def constraint_typed_names(self) -> tuple[GlobalTypedNameReference, ...]:
        """The typed names of this position's constraint requirements, in source order."""
        if self.constraints is None:
            return ()
        return tuple(req.typed_global_name for req in self.constraints.requirements)


class NameContent(ASTNode, abc.ABC):
    """Base class for name content nodes (local or global)."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """The inner content as it appears in the source."""


class LocalNameContent(NameContent):
    """Represents a local name."""

    name: str

    def __post_init__(self):
        """Intern the local name."""
        self.name = sys.intern(self.name)

    @property
    @override
    def source_name(self) -> str:
        return self.name


class LocalPositionDefinition(ASTNode):
    """Represents a local position definition."""

    typed_name: LocalTypedNameReference
    constraints: PositionConstraintBlock | None = None

    @classmethod
    def from_name(
        cls,
        *,
        local_name: LocalNameContent,
        location: SourceLocation,
        constraints: PositionConstraintBlock | None = None,
    ) -> Self:
        """Initialize with a local name, wrapping it in a typed name."""
        return cls(
            typed_name=LocalTypedNameReference(
                name_type=name_types.NameType.POSITION,
                name_content=local_name,
                location=SourceLocation.from_definition_name(
                    local_name, name_types.NameType.POSITION
                ),
            ),
            location=location,
            constraints=constraints,
        )

    @property
    def constraint_typed_names(self) -> tuple[GlobalTypedNameReference, ...]:
        """The typed names of this position's constraint requirements, in source order."""
        if self.constraints is None:
            return ()
        return tuple(req.typed_global_name for req in self.constraints.requirements)


type AnyPositionDefinition = PositionDefinition | LocalPositionDefinition


class ViewDefinition(ASTNode):
    """Represents a view definition."""

    typed_name: LocalTypedNameReference
    is_input: bool
    is_output: bool
    constraints: PositionConstraintBlock

    @classmethod
    def from_name(
        cls,
        *,
        local_name: LocalNameContent,
        is_input: bool,
        is_output: bool,
        constraints: PositionConstraintBlock,
        location: SourceLocation,
    ) -> Self:
        """Initialize with a local name, wrapping it in a typed name."""
        return cls(
            typed_name=LocalTypedNameReference(
                name_type=name_types.NameType.VIEW,
                name_content=local_name,
                location=SourceLocation.from_definition_name(
                    local_name, name_types.NameType.VIEW
                ),
            ),
            is_input=is_input,
            is_output=is_output,
            constraints=constraints,
            location=location,
        )


# Struct-generated constructors prevent automatic covariance inference.
NameContentT_co = TypeVar("NameContentT_co", bound=NameContent, covariant=True)


class TypedName(ASTNode, Generic[NameContentT_co], kw_only=True):  # noqa: UP046
    """Represents a typed name (local or global)."""

    name_type: name_types.NameType
    name_content: Final[NameContentT_co]
    _source_typed_name: str = ""

    def __post_init__(self):
        """Build the interned source-form typed name."""
        self._source_typed_name = sys.intern(
            f"{self.name_type.value}<{self.name_content.source_name}>"
        )

    @property
    def source_typed_name(self) -> str:
        """The typed-name text as it appears in the source."""
        return self._source_typed_name

    @property
    def full_typed_name(self) -> str:
        """The canonical typed-name text including the effective FQUN and path."""
        return self._source_typed_name


GlobalNameContentT_co = TypeVar(
    "GlobalNameContentT_co", bound="GlobalNameContent[Fqun | None]", covariant=True
)


class GlobalTypedName(
    TypedName[GlobalNameContentT_co],
    Generic[GlobalNameContentT_co],  # noqa: UP046
):
    """A typed global name, at either a definition site or a reference site."""


class GlobalTypedNameReference(GlobalTypedName["ReferenceGlobalNameContent"]):
    """Represents a typed global name reference."""

    enclosing_fqun: Fqun
    _full_typed_name: str = ""

    def __post_init__(self):
        """Build the interned canonical typed name."""
        super().__post_init__()
        fqun = self.name_content.fqun or self.enclosing_fqun
        self._full_typed_name = sys.intern(
            f"{self.name_type.value}<{fqun.canonical}:{self.name_content.path.name}>"
        )

    @property
    @override
    def full_typed_name(self) -> str:
        return self._full_typed_name

    @property
    def effective_fqun(self) -> Fqun:
        """The reference's FQUN, or the enclosing definition's when none is written."""
        return self.name_content.fqun or self.enclosing_fqun

    def source_form_in_universe(self, caller_fqun: Fqun) -> str:
        """Get the string form of the name as it would be written in source in the specified universe."""
        if self.effective_fqun.canonical != caller_fqun.canonical:
            return self.full_typed_name
        return self.source_typed_name


class LocalTypedNameReference(TypedName[LocalNameContent]):
    """Represents a typed local name reference."""


type TypedNameReference = GlobalTypedNameReference | LocalTypedNameReference


class SourceFormTypedNameParts(msgspec.Struct, frozen=True):
    """Source-form parts parsed from one full typed name."""

    name_type: name_types.NameType
    source_name: str
    is_global: bool


def source_form_typed_name_parts(
    typed_name: str,
    current_fqun: str,
) -> SourceFormTypedNameParts:
    """Return source-form parts for one full typed name."""
    name_type, canonical_name = typed_name[:-1].split("<", 1)
    is_global = canonical_name.startswith("/") or ":/" in canonical_name
    source_name = canonical_name.removeprefix(current_fqun + ":")
    return SourceFormTypedNameParts(
        name_type=name_types.NameType(name_type),
        source_name=source_name,
        is_global=is_global,
    )


def source_form_chained_name(
    chained_name: chained_name.ChainedNameTuple,
    current_fqun: str,
) -> str:
    """Return a canonical chained-name tuple in source form for one universe."""
    source_names: list[str] = []
    for typed_name in chained_name:
        parts = source_form_typed_name_parts(typed_name, current_fqun)
        source_names.append(f"{parts.name_type.value}<{parts.source_name}>")
    return "::".join(source_names)


ChainedNameTupleT_co = TypeVar(
    "ChainedNameTupleT_co",
    bound=chained_name.ChainedNameTuple,
    covariant=True,
    default=chained_name.ChainedNameTuple,
)


class ChainedName(ASTNode, abc.ABC, Generic[ChainedNameTupleT_co]):
    """A chain of typed name references joined by ::.

    Treat location and typed_names as immutable after construction so that
    cached canonical forms and dictionary keys remain valid.
    """

    typed_names: tuple[TypedNameReference, ...]
    # A covariant type in a mutable field is safe here only because nothing
    # writes it through a chained name of a wider kind: only this class's
    # property and the construction of a concrete kind set it.
    _canonical_chained_name_tuple: ChainedNameTupleT_co | None = None
    _canonical_chained_name: str | None = None

    def __post_init__(self):
        """Require at least one typed name."""
        if not self.typed_names:
            raise ValueError("ChainedName must contain at least one typed name")

    # These remain lazy because computing them for every new chain was a top
    # hotspot in compilation profiles. The values are deterministic over the
    # immutable typed_names, so a benign race recomputes an equal value.
    @property
    def canonical_chained_name_tuple(self) -> ChainedNameTupleT_co:
        """The canonical typed names in this chain."""
        if self._canonical_chained_name_tuple is None:
            self._canonical_chained_name_tuple = self._tag(
                chained_name.ChainedNameTuple(
                    tuple([elem.full_typed_name for elem in self.typed_names])
                )
            )
        return self._canonical_chained_name_tuple

    @abc.abstractmethod
    def _tag(
        self, canonical_names: chained_name.ChainedNameTuple
    ) -> ChainedNameTupleT_co:
        """Tag canonical typed names with this chained name's kind."""

    @property
    def canonical_chained_name(self) -> str:
        """The canonical chained name."""
        if self._canonical_chained_name is None:
            self._canonical_chained_name = "::".join(self.canonical_chained_name_tuple)
        return self._canonical_chained_name

    @property
    def source_chained_name(self) -> str:
        """The chained name text as it appears in the source."""
        return "::".join(elem.source_typed_name for elem in self.typed_names)

    @property
    def starts_with_global(self) -> bool:
        """Whether the chain's first element is a global reference."""
        return isinstance(self.typed_names[0], GlobalTypedNameReference)

    def get_last_action(self) -> GlobalTypedNameReference | None:
        """Return the last action element in the chain, or None."""
        for elem in reversed(self.typed_names):
            if elem.name_type == name_types.NameType.ACTION and isinstance(
                elem, GlobalTypedNameReference
            ):
                return elem
        return None

    def get_chain_to_last_action(self) -> ActionReference | None:
        """Return everything up to and including the last action element, or None."""
        index = chained_name.last_action_index(self.canonical_chained_name_tuple)
        if index is None:
            return None
        return ActionReference(
            location=self.location,
            typed_names=self.typed_names[: index + 1],
            # A prefix of self's canonical tuple is exactly the result's, so
            # slice it here instead of making the result recompute it.
            _canonical_chained_name_tuple=chained_name.action(
                self.canonical_chained_name_tuple[: index + 1]
            ),
        )

    def parent_position(self) -> PositionReference | None:
        """Return the nearest parent position, or None for single-element chains."""
        index = chained_name.parent_position_index(self.canonical_chained_name_tuple)
        if index is None:
            return None
        return PositionReference(
            location=self.location,
            typed_names=self.typed_names[: index + 1],
            # A prefix of self's canonical tuple is exactly the parent's,
            # so slice it here instead of making the parent recompute it.
            _canonical_chained_name_tuple=chained_name.position(
                self.canonical_chained_name_tuple[: index + 1]
            ),
        )

    def source_form_in_universe(self, caller_fqun: Fqun) -> str:
        """Get the string form of the name as it would be written in source in the specified universe."""
        parts: list[str] = []
        for elem in self.typed_names:
            if isinstance(elem, GlobalTypedNameReference):
                parts.append(elem.source_form_in_universe(caller_fqun))
            else:
                parts.append(elem.source_typed_name)
        return "::".join(parts)

    def with_prefix(self, prefix: ChainedName) -> Self:
        """Return a copy of ``self`` with ``prefix.typed_names`` prepended.

        The result has the same subclass as ``self`` (e.g. a
        ``PositionReference`` stays a ``PositionReference``).
        """
        return type(self)(
            location=self.location,
            typed_names=prefix.typed_names + self.typed_names,
            # Specifying this here shaves 10% of the time off a full compile of a complex
            # multi-action compile, mostly because it saves recomputing the canonical
            # chained_name_tuple over and over for requirement checks. (Concatenating
            # these two tuples is much faster than generating the tuple from the typed
            # names.)
            _canonical_chained_name_tuple=chained_name.with_prefix(
                self.canonical_chained_name_tuple, prefix.canonical_chained_name_tuple
            ),
        )

    def without_prefix(self, prefix: ChainedName) -> Self:
        """Return a copy of ``self`` with ``prefix``'s typed names removed from the front.

        ``prefix`` must be a prefix of ``self``. The result has the same
        subclass as ``self``.
        """
        return type(self)(
            location=self.location,
            typed_names=self.typed_names[len(prefix.typed_names) :],
            # Slicing the canonical tuple avoids recomputing it, for the same
            # reason with_prefix passes it.
            _canonical_chained_name_tuple=self._tag(
                chained_name.without_prefix(
                    self.canonical_chained_name_tuple,
                    prefix.canonical_chained_name_tuple,
                )
            ),
        )

    def with_position_suffix(self, *names: TypedNameReference) -> PositionReference:
        """Return a PositionReference extending this chain with ``names`` appended.

        The appended chain must end in a position; the PositionReference
        constructor enforces that.
        """
        return PositionReference(
            location=self.location,
            typed_names=self.typed_names + names,
            _canonical_chained_name_tuple=chained_name.position(
                self.canonical_chained_name_tuple
                + tuple([name.full_typed_name for name in names])
            ),
        )

    def with_action_suffix(self, *names: TypedNameReference) -> ActionReference:
        """Return an ActionReference extending this chain with ``names`` appended.

        The appended chain must end in an action; the ActionReference
        constructor enforces that.
        """
        return ActionReference(
            location=self.location,
            typed_names=self.typed_names + names,
            _canonical_chained_name_tuple=chained_name.action(
                self.canonical_chained_name_tuple
                + tuple([name.full_typed_name for name in names])
            ),
        )

    def in_caller(self, caller_chain: ChainedName) -> Self:
        """Get the chained name of a contracted position from the perspective of the caller."""
        caller_ends_with_action = (
            caller_chain.typed_names[-1].name_type == name_types.NameType.ACTION
        )
        if self.starts_with_global and caller_ends_with_action:
            parent = caller_chain.parent_position()
            if parent is None:
                return self
            return self.with_prefix(parent)
        return self.with_prefix(caller_chain)


class PositionReference(ChainedName[chained_name.PositionReferenceTuple]):
    """Represents a position reference, possibly chained with ::."""

    from_source: bool = False

    def __post_init__(self):
        """Require a position as the final typed name."""
        super().__post_init__()
        if (
            not self.from_source
            and self.typed_names[-1].name_type != name_types.NameType.POSITION
        ):
            raise ValueError(
                f"Last element of a PositionReference must be a position: {self.source_chained_name}"
            )

    def position_prefix(self, name_count: int) -> PositionReference:
        """Return the position prefix containing ``name_count`` typed names."""
        if name_count == len(self.typed_names):
            return self
        return PositionReference(
            location=self.location,
            typed_names=self.typed_names[:name_count],
            _canonical_chained_name_tuple=chained_name.position_prefix(
                self.canonical_chained_name_tuple, name_count
            ),
        )

    @override
    def _tag(
        self, canonical_names: chained_name.ChainedNameTuple
    ) -> chained_name.PositionReferenceTuple:
        return chained_name.position(canonical_names)


class ActionReference(ChainedName[chained_name.ActionReferenceTuple]):
    """Represents a chained name known to end with an action.

    Unlike PositionReference, the parser never produces this directly; the
    compiler synthesizes it for chains it has determined end in an action.
    """

    def __post_init__(self):
        """Require an action as the final typed name."""
        super().__post_init__()
        if self.typed_names[-1].name_type != name_types.NameType.ACTION:
            raise ValueError(
                f"Last element of an ActionReference must be an action: {self.source_chained_name}"
            )

    @override
    def get_last_action(self) -> GlobalTypedNameReference:
        """Return the action this chain ends with."""
        # Every action name is global, and construction checked that the chain ends
        # with an action, so its last element is that action.
        return cast("GlobalTypedNameReference", self.typed_names[-1])

    @override
    def _tag(
        self, canonical_names: chained_name.ChainedNameTuple
    ) -> chained_name.ActionReferenceTuple:
        return chained_name.action(canonical_names)


class ParticleStatement(ASTNode):
    """Base class for statements that operate on a target particle position."""

    target_position: PositionReference


class CreateParticleStatement(ParticleStatement):
    """Represents a 'create a particle in' statement."""


class MoveParticleStatement(ParticleStatement):
    """Represents a 'move the particle in ... to' statement."""

    source_position: PositionReference


class DestroyParticleStatement(ParticleStatement):
    """Represents a 'destroy the particle in' statement."""


class Literal(ASTNode):
    """A literal's Potential Literal reference and decoded content."""

    potential_literal: GlobalTypedNameReference
    content: str

    def content_character_location(self, index: int) -> SourceLocation:
        """Return the source location of the content character at ``index``."""
        # ", \, and newlines can only appear in content through two-character
        # escapes, so each one before ``index`` adds one source column.
        escaped_count = sum(1 for char in self.content[:index] if char in '"\\\n')
        # The Potential Literal reference ends at the opening quote.
        column = self.potential_literal.location.end_column + 1 + index + escaped_count
        return SourceLocation(
            line=self.location.line,
            column=column,
            end_line=self.location.line,
            end_column=column + 1,
            file_path=self.location.file_path,
        )


class ValueSettingStatement(ParticleStatement):
    """Represents a 'set the value of ... to' statement."""

    source: PositionReference | Literal


type ActionStatement = (
    LocalPositionDefinition
    | CreateParticleStatement
    | MoveParticleStatement
    | DestroyParticleStatement
    | ValueSettingStatement
    | OperationExecutionStatement
)


class OperationArgumentStatement(ASTNode):
    """Represents a 'with view<...> looking at' statement."""

    view: LocalTypedNameReference
    looking_at: PositionReference | LocalTypedNameReference | Literal


class OperationExecutionStatement(ASTNode):
    """Represents an 'execute the operation<...>' or 'execute the encoding_operation<...>' statement."""

    operation: GlobalTypedNameReference
    arguments: tuple[OperationArgumentStatement, ...]


class EncodingOperationExecutionStatement(ASTNode):
    """Represents the 'execute the encoding operation' statement."""


class ComputerOperationExecutionStatement(ASTNode):
    """Represents the 'execute the computer operation' statement."""


type OperationStatement = (
    OperationExecutionStatement
    | EncodingOperationExecutionStatement
    | ComputerOperationExecutionStatement
)


class PositionRequirementStatement(ASTNode):
    """Represents a position requirement statement in a constraints block."""

    typed_global_name: GlobalTypedNameReference


class QualityImplicationStatement(ASTNode):
    """Represents a quality implication statement."""

    typed_global_name: GlobalTypedNameReference


class PositionConstraintBlock(ASTNode):
    """Represents a position constraint block."""

    requirements: tuple[PositionRequirementStatement, ...]
    as_set: frozenset[str] = frozenset()

    def __post_init__(self):
        """Build the set of canonical required names."""
        self.as_set = frozenset(
            requirement.typed_global_name.full_typed_name
            for requirement in self.requirements
        )

    @property
    def value_constraint(self) -> GlobalTypedNameReference | None:
        """The first value this block requires, if any."""
        for requirement in self.requirements:
            if requirement.typed_global_name.name_type == name_types.NameType.VALUE:
                return requirement.typed_global_name
        return None


class GlobalPathName(ASTNode):
    """Represents the path portion of a global name."""

    name: str

    def __post_init__(self):
        """Intern the global path name."""
        # The parser supplies the token's string value because sys.intern rejects
        # token objects.
        self.name = sys.intern(self.name)

    @property
    def relative_path(self) -> define_path.DefinePath:
        """The path as a relative DefinePath."""
        return define_path.DefinePath(self.name[1:])

    def file_path(
        self,
        root: define_path.DefinePath = define_path.EMPTY,
    ) -> define_path.DefinePath:
        """Return the .dfn file path, prefixed by root."""
        return root / self.relative_path.with_suffix(constants.DEFINE_FILE_SUFFIX)


class PositionPresenceStatement(ASTNode):
    """Represents a position presence statement."""

    typed_name: LocalTypedNameReference
    position_reference: PositionReference

    @classmethod
    def from_typed_name(
        cls, *, location: SourceLocation, typed_name: LocalTypedNameReference
    ) -> Self:
        """Create a position presence statement for a typed name."""
        return cls(
            location=location,
            typed_name=typed_name,
            position_reference=PositionReference(
                typed_names=(typed_name,),
                location=typed_name.location,
                from_source=True,
            ),
        )


class ConstructorConditionStatement(ASTNode):
    """Represents a constructor condition statement."""


class DestructorConditionStatement(ASTNode):
    """Represents a destructor condition statement."""


type TriggerConditionStatement = (
    PositionPresenceStatement
    | ConstructorConditionStatement
    | DestructorConditionStatement
)


class TriggerConditionsBlock(ASTNode):
    """Represents a trigger conditions block."""

    condition: TriggerConditionStatement


class ActionStatementsBlock(ASTNode):
    """Represents an action statements block."""

    statements: tuple[ActionStatement, ...]


class ActionDefinition(QualityDefinition):
    """Represents an action definition."""

    interface_positions: tuple[LocalPositionDefinition, ...]
    trigger_conditions: TriggerConditionsBlock
    action_statements: ActionStatementsBlock
    # Computed properties
    interface_positions_by_name: dict[str, LocalPositionDefinition] = msgspec.field(
        default_factory=dict
    )
    trigger_position: LocalPositionDefinition | None = None

    @classmethod
    def from_name(
        cls,
        *,
        name: DefinitionGlobalNameContent,
        location: SourceLocation,
        quality_implications: tuple[QualityImplicationStatement, ...],
        interface_positions: tuple[LocalPositionDefinition, ...],
        trigger_conditions: TriggerConditionsBlock,
        action_statements: ActionStatementsBlock,
    ) -> Self:
        """Initialize with a global name, wrapping it in a typed definition name."""
        return cls(
            typed_name=GlobalTypedNameInDefinition(
                name_type=name_types.NameType.ACTION,
                name_content=name,
                location=SourceLocation.from_definition_name(
                    name, name_types.NameType.ACTION
                ),
            ),
            quality_implications=quality_implications,
            location=location,
            interface_positions=interface_positions,
            trigger_conditions=trigger_conditions,
            action_statements=action_statements,
        )

    def __post_init__(self):
        """Populate the interface-position lookup values."""
        # Computing these up front guarantees later thread-safety for accessing
        # this information instead of creating multiple cached copies across threads.
        for local_def in self.interface_positions:
            local_name = local_def.typed_name.source_typed_name
            if local_name not in self.interface_positions_by_name:
                self.interface_positions_by_name[local_name] = local_def
        self.trigger_position = self._compute_trigger_position()

    @property
    def interface_position_names(self) -> tuple[TypedName[NameContent], ...]:
        """The TypedName objects for all interface positions."""
        return tuple(pos.typed_name for pos in self.interface_positions)

    def _compute_trigger_position(self) -> LocalPositionDefinition | None:
        condition = self.trigger_conditions.condition
        if not isinstance(condition, PositionPresenceStatement):
            return None
        trigger_name = condition.typed_name.source_typed_name
        return self.interface_positions_by_name.get(trigger_name)

    @property
    def trigger_position_reference(self) -> PositionReference | None:
        """The trigger condition's PositionReference, if valid."""
        condition = self.trigger_conditions.condition
        if self.trigger_position is None or not isinstance(
            condition, PositionPresenceStatement
        ):
            return None
        return condition.position_reference

    @property
    def is_constructor(self) -> bool:
        """Whether this action triggers when its particle is created."""
        return isinstance(
            self.trigger_conditions.condition, ConstructorConditionStatement
        )

    @property
    def is_destructor(self) -> bool:
        """Whether this action triggers when its particle is destroyed."""
        return isinstance(
            self.trigger_conditions.condition, DestructorConditionStatement
        )


class Multiverse(ASTNode):
    """Represents a multiverse name."""

    name: str

    def __post_init__(self):
        """Intern the multiverse name."""
        self.name = sys.intern(str(self.name))


class Universe(ASTNode):
    """Represents a universe name."""

    name: str

    def __post_init__(self):
        """Intern the universe name."""
        self.name = sys.intern(str(self.name))


class Authority(ASTNode):
    """Represents an authority (domain plus optional path)."""

    name: str

    def __post_init__(self):
        """Intern the authority name."""
        self.name = sys.intern(str(self.name))


class Fqun(ASTNode):
    """Represents a fully-qualified universe name."""

    multiverse: Multiverse | None
    authority: Authority | None
    universe: Universe
    canonical: str = ""

    def __post_init__(self):
        """Build the interned canonical FQUN."""
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
        self.canonical = sys.intern(value)


FqunT_co = TypeVar("FqunT_co", bound=Fqun | None, covariant=True)


class GlobalNameContent(NameContent, Generic[FqunT_co]):  # noqa: UP046
    """Base class for global name-like nodes."""

    fqun: Final[FqunT_co]
    path: GlobalPathName

    @property
    @override
    def source_name(self) -> str:
        if self.fqun is not None:
            return f"{self.fqun.canonical}:{self.path.name}"
        return self.path.name


class DefinitionGlobalNameContent(GlobalNameContent[Fqun]):
    """Represents a global name at a definition site."""


class ReferenceGlobalNameContent(GlobalNameContent[Fqun | None]):
    """Represents a global name at a reference site."""


class GlobalTypedNameInDefinition(GlobalTypedName[DefinitionGlobalNameContent]):
    """Represents a typed global name at a definition site."""
