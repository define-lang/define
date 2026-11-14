"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import hashlib
import keyword
import re
import typing
from pathlib import Path

from define.compiler import ast, constants, name_types
from define.compiler.codegen.literal.python import renderer

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from define.compiler import chained_name
    from define.compiler.data_structures import define_path
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )

_AUTHORITY_CHAR_TABLE = str.maketrans({".": "_", "/": "__", "-": "_", "~": "_"})
# These authorities translate to distinct segments, because each run of
# underscores in their segments is one underscore for a dot or two for a slash.
_READABLE_AUTHORITY = re.compile(r"[a-z0-9]+(?:[./][a-z0-9]+)*")
# Separates a translated authority from the digest of the original. Readable
# authority segments never contain it, so the two forms never collide.
_AUTHORITY_DIGEST_SEPARATOR = "___"
# An Encoding Operation's function lives in the module of its path's parent,
# beside the packages of its sibling path segments. The prefix keeps its name
# from being a package name, a keyword, or a built-in, so that every function
# and module name depends only on the Define name it is for.
_ENCODING_OPERATION_PREFIX = "encoding_"
# A module-name component that starts with one of these gets one more leading
# `_`, so that no module-name component starts with a function's prefix.
_ESCAPED_COMPONENT_PREFIXES = ("_", _ENCODING_OPERATION_PREFIX)
# Local names start with a prefix so that no local name is a keyword, a
# built-in, or a name the generated method itself uses.
VIEW_PREFIX = "view_"
POSITION_PREFIX = "position_"

RUN_DESTRUCTORS_PREFIX = "run_destructors_"
DESTROY_PREFIX = "destroy_"
RUN_GUARANTEED_PARTICLE_DESTRUCTORS_PREFIX = "run_guaranteed_particle_destructors_"
# A method name joins one part per typed name in a chained name with this.
_CHAIN_PART_SEPARATOR = "__"
# Within one part, the typed name's type, path components, and any repeat count
# are joined with this.
_NAME_PART_SEPARATOR = "_"
# The type a chained name's first part uses when it starts with a global
# position, to tell it apart from a local position with the same name.
_GLOBAL_POSITION_TYPE = "global_position"
_PATH_SEPARATOR = "/"

# Filesystems commonly limit each path component to 255 bytes. Python
# identifiers have no such limit, but a module's dotted name is also written
# into generated `import` statements, so every component of that dotted name
# must already respect the filesystem limit for the import to resolve to the
# file this compiler writes.
_MODULE_COMPONENT_BYTE_LIMIT = 255
# 8 bytes keeps distinct components apart well past the number of definitions
# a single program can hold, and the digest must stay a pure function of the
# component so that truncation never makes a module name depend on what else
# was compiled.
_MODULE_COMPONENT_DIGEST_BYTES = 8
_QUALITY_NAME_TYPES = (name_types.NameType.POSITION, name_types.NameType.ACTION)


def _truncate_module_component(component: str) -> str:
    """Shorten one module-name component to fit the filesystem byte limit.

    The digest covers the full original component, so two components that
    share an over-long prefix still truncate to distinct results.
    """
    # Every component has already passed structural name validation, which
    # permits only ASCII characters in module-name components.
    if len(component) <= _MODULE_COMPONENT_BYTE_LIMIT:
        return component
    encoded = component.encode()
    digest = hashlib.blake2b(encoded, digest_size=_MODULE_COMPONENT_DIGEST_BYTES)
    suffix = f"_{digest.hexdigest()}"
    prefix_byte_limit = _MODULE_COMPONENT_BYTE_LIMIT - len(suffix)
    prefix = component[:prefix_byte_limit]
    return prefix + suffix


def _escape_module_component(component: str) -> str:
    """Make a module-name component importable without colliding with another component or a function.

    Python keywords cannot appear in an ``import`` statement. Appending ``_``
    to every component that already ends in ``_`` keeps the escaping one-to-one.
    Prepending ``_`` to every component that starts with a function's prefix
    or with ``_`` keeps every component from being a function's name, and is
    also one-to-one.
    """
    if component.startswith(_ESCAPED_COMPONENT_PREFIXES):
        component = "_" + component
    if keyword.iskeyword(component) or component.endswith("_"):
        return component + "_"
    return component


def _local_name_part(name_type: name_types.NameType, name: str) -> str:
    """Return the part of a method name for a local typed name."""
    return f"{name_type.value}{_NAME_PART_SEPARATOR}{name}"


def _global_name_part(
    index: int, name_type: name_types.NameType, path: Sequence[str]
) -> str:
    """Return the part of a method name for a global typed name at ``index`` in a chained name, whose path has the components ``path``."""
    type_part = name_type.value
    if index == 0 and name_type == name_types.NameType.POSITION:
        type_part = _GLOBAL_POSITION_TYPE
    return f"{type_part}{_NAME_PART_SEPARATOR}{_NAME_PART_SEPARATOR.join(path)}"


def _tuple_chained_name_part(chain: chained_name.ChainedNameTuple) -> str:
    """Return the part of a method name that identifies a chained-name tuple."""
    parts: list[str] = []
    for index, typed_name in enumerate(chain):
        typed_name_parts = ast.source_form_typed_name_parts(typed_name, "")
        if typed_name_parts.is_global:
            # A global's canonical name is its universe, then its path.
            path = typed_name_parts.source_name.split(_PATH_SEPARATOR, 1)[1]
            parts.append(
                _global_name_part(
                    index, typed_name_parts.name_type, path.split(_PATH_SEPARATOR)
                )
            )
        else:
            parts.append(
                _local_name_part(
                    typed_name_parts.name_type, typed_name_parts.source_name
                )
            )
    return _CHAIN_PART_SEPARATOR.join(parts)


def _chained_name_part(chain: ast.PositionReference) -> str:
    """Return the part of a method name that identifies a chained name."""
    parts: list[str] = []
    for index, typed_name in enumerate(chain.typed_names):
        if isinstance(typed_name, ast.GlobalTypedNameReference):
            parts.append(
                _global_name_part(
                    index,
                    typed_name.name_type,
                    typed_name.name_content.path.relative_path.parts,
                )
            )
        else:
            parts.append(
                _local_name_part(typed_name.name_type, typed_name.name_content.name)
            )
    return _CHAIN_PART_SEPARATOR.join(parts)


def _with_occurrence(name: str, occurrence: int) -> str:
    """Return ``name``, prefixed with ``occurrence`` when it repeats."""
    if occurrence > 1:
        return f"{occurrence}{_NAME_PART_SEPARATOR}{name}"
    return name


def authority_segment(authority: str) -> str:
    """Convert an authority to a Python module segment that no other authority gets.

    An authority made of letters and digits separated by single dots and
    slashes keeps its readable form. Every other authority loses characters in translation, so a
    digest of the original authority keeps it distinct.
    """
    # The segment must stay a pure function of the authority so that an
    # authority's module name never depends on what else was compiled.
    segment = authority.translate(_AUTHORITY_CHAR_TABLE)
    if _READABLE_AUTHORITY.fullmatch(authority) is None:
        digest = hashlib.blake2b(
            authority.encode(), digest_size=_MODULE_COMPONENT_DIGEST_BYTES
        )
        segment += _AUTHORITY_DIGEST_SEPARATOR + digest.hexdigest()
    return _escape_module_component(segment)


@typing.final
class LocalNameAllocator:
    """Allocate unique local names within one generated Python method."""

    def __init__(self):
        """Start with no names allocated."""
        self._used: set[str] = set()
        # The next numeric suffix to try for each candidate that was already
        # used. Numbering, rather than lengthening a name until it is free,
        # keeps the K-th use of a candidate from taking O(K) probes and a name
        # O(K) characters long.
        self._next_suffix: dict[str, int] = {}

    def allocate(self, candidate: str) -> str:
        """Return ``candidate``, or the first free numbered form of it if it is used."""
        name = candidate
        if name in self._used:
            suffix = self._next_suffix.get(candidate, 2)
            name = f"{candidate}_{suffix}"
            while name in self._used:
                suffix += 1
                name = f"{candidate}_{suffix}"
            self._next_suffix[candidate] = suffix + 1
        self._used.add(name)
        return name

    def reserve_module_first_names(self, modules: Iterable[str]):
        """Reserve the first name of each imported module."""
        # Assigning a local variable shadows an imported name throughout the
        # function, including before the assignment.
        self._used.update(module.split(".", 1)[0] for module in modules)


def file_path_for_module(module_name: str) -> Path:
    """Convert a dotted module name to an __init__.py file path.

    Callers must obtain ``module_name`` from ``NameConverter``, which already
    truncates each component to the filesystem byte limit.
    """
    return Path(*module_name.split(".")) / "__init__.py"


def _path_to_pascal(path: define_path.DefinePath) -> str:
    """Convert a definition path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )


class NameConverter:
    """Converts Define names to safe Python identifiers.

    A single instance is shared across an entire code generation run to ensure
    consistent naming (e.g., a class name used in a quality assignment list matches the
    class definition).
    """

    _class_names: dict[tuple[define_path.DefinePath, str], str]
    _class_references: dict[str, renderer.ClassReference]
    # The module name components that name each FQUN, keyed by its canonical
    # form.
    _universe_module_name_parts: dict[str, list[str]]

    def __init__(self):
        """Initialize with empty name caches."""
        self._universe_module_name_parts = {}
        self._class_names = {}
        self._class_references = {}

    def function_reference(
        self,
        typed_global_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> renderer.FunctionReference:
        """Build a reference to a generated function, which lives in the module of its path's parent."""
        fqun = self._fqun(typed_global_name)
        parent_segments = typed_global_name.name_content.path.relative_path.parts[:-1]
        return renderer.FunctionReference(
            function_name=self._function_name(typed_global_name),
            module_name=".".join(self._module_name_parts(fqun, parent_segments)),
        )

    @staticmethod
    def _function_name(
        typed_global_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> str:
        return (
            _ENCODING_OPERATION_PREFIX
            + typed_global_name.name_content.path.relative_path.parts[-1]
        )

    @staticmethod
    def _fqun(
        typed_global_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> ast.Fqun:
        if isinstance(typed_global_name, ast.GlobalTypedNameReference):
            return typed_global_name.effective_fqun
        return typing.cast(
            "ast.DefinitionGlobalNameContent", typed_global_name.name_content
        ).fqun

    def class_name(
        self,
        typed_global_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> str:
        """Convert a global name to a PascalCase class name ending in its name type.

        Results are cached so the same name always returns the same class name.
        """
        # Definitions of different name types at the same path share a Python
        # module, so the name type keeps their classes apart.
        return self._class_name(
            typed_global_name.name_content.path.relative_path,
            typed_global_name.name_type.value.capitalize(),
        )

    def destruction_contract_class_name(self, path: define_path.DefinePath) -> str:
        """Convert an action path to its destruction-contract class name."""
        return self._class_name(path, "DestructionContracts")

    def _class_name(self, path: define_path.DefinePath, suffix: str) -> str:
        key = (path, suffix)
        if key in self._class_names:
            return self._class_names[key]
        name = _path_to_pascal(path) + suffix
        self._class_names[key] = name
        return name

    def referenced_modules(
        self,
        position: ast.ChainedName,
    ) -> Iterator[str]:
        """Yield modules referenced by a position or action."""
        for name in position.typed_names:
            if ast.is_global_reference(name):
                yield self.class_reference(name).module_name

    def _module_name_parts(
        self, fqun: ast.Fqun, path_segments: Sequence[str]
    ) -> list[str]:
        """Compute module name segments from an FQUN and definition path segments."""
        parts = self._universe_module_name_parts.get(fqun.canonical)
        if parts is None:
            parts = self._universe_parts(fqun)
            self._universe_module_name_parts[fqun.canonical] = parts
        parts = parts.copy()
        for segment in path_segments:
            parts.append(_truncate_module_component(_escape_module_component(segment)))
        return parts

    @staticmethod
    def _universe_parts(fqun: ast.Fqun) -> list[str]:
        parts: list[str] = []
        # Only the standard universe is written without an authority.
        if fqun.authority is not None:
            if fqun.multiverse is not None:
                parts.append(_escape_module_component(fqun.multiverse.name))
            else:
                parts.append(constants.DEFAULT_MULTIVERSE)
            parts.append(authority_segment(fqun.authority.name))
        parts.append(_escape_module_component(fqun.universe.name))
        return [_truncate_module_component(part) for part in parts]

    def module_name(self, name_content: ast.DefinitionGlobalNameContent) -> str:
        """Compute the dotted Python module name for a global definition."""
        parts = self._module_name_parts(
            name_content.fqun, name_content.path.relative_path.parts
        )
        return ".".join(parts)

    def assigned_quality_class_references(
        self,
        block: ast.QualityAssignmentBlock | None,
    ) -> list[renderer.ClassReference]:
        """Extract references to the position and action classes that a Quality Assignment Block assigns."""
        if block is None:
            return []
        # Values and encodings have no generated classes, because literals are
        # already in their values' encodings in generated code.
        return [
            self.class_reference(statement.typed_global_name)
            for statement in block.statements
            if statement.typed_global_name.name_type in _QUALITY_NAME_TYPES
        ]

    def implied_qualities_to_class_references(
        self,
        quality_implications: Iterable[ast.QualityImplicationStatement],
    ) -> list[renderer.ClassReference]:
        """Extract class references from a list of quality implication statements."""
        return [
            self.class_reference(implication.typed_global_name)
            for implication in quality_implications
        ]

    def class_reference(
        self,
        typed_global_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> renderer.ClassReference:
        """Build a reference to one generated global class."""
        canonical_name = typed_global_name.full_typed_name
        existing = self._class_references.get(canonical_name)
        if existing is not None:
            return existing
        name_content = typed_global_name.name_content
        cls_name = self.class_name(typed_global_name)
        module_name = ".".join(
            self._module_name_parts(
                self._fqun(typed_global_name), name_content.path.relative_path.parts
            )
        )
        class_reference = renderer.ClassReference(
            class_name=cls_name, module_name=module_name
        )
        self._class_references[canonical_name] = class_reference
        return class_reference

    @staticmethod
    def guaranteed_particle_destructors_method_name(
        position_in_action: chained_name.PositionReferenceTuple,
    ) -> str:
        """Return the name of an action's method that runs the Destructors for what it left at and below one position of its contract."""
        return RUN_GUARANTEED_PARTICLE_DESTRUCTORS_PREFIX + _tuple_chained_name_part(
            position_in_action
        )

    @staticmethod
    def destruction_method_names(
        contracts: Iterable[destruction_contract.DestructionContract],
    ) -> dict[destruction_contract.DestructionContract, str]:
        """Allocate contribution names from each particle's contracted origin."""
        names: dict[destruction_contract.DestructionContract, str] = {}
        occurrences: dict[str, int] = {}
        for contract in contracts:
            candidate = _chained_name_part(contract.contracted_position)
            occurrence = occurrences.get(candidate, 0) + 1
            occurrences[candidate] = occurrence
            # Separate invocations can propagate the same Destruction Fact.
            names[contract] = _with_occurrence(candidate, occurrence)
        return names
