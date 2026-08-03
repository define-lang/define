"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import builtins
import hashlib
import keyword
import typing
from dataclasses import dataclass
from pathlib import Path

from define.compiler import constants

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import define_path

_PYTHON_BUILTINS: frozenset[str] = frozenset(vars(builtins))

_AUTHORITY_CHAR_TABLE = str.maketrans(".-~/", "____")
_EXECUTION_CLASS_SUFFIX = "Execution"
_GUARANTEES_CLASS_SUFFIX = "Guarantees"

# Filesystems commonly limit each path component to 255 bytes. Python
# identifiers have no such limit, but a module's dotted name is also written
# into generated `import` statements, so every component of that dotted name
# must already respect the filesystem limit for the import to resolve to the
# file this compiler writes.
_MODULE_COMPONENT_BYTE_LIMIT = 255
# 8 bytes keeps distinct components apart well past the number of definitions
# a single program can hold, and the digest must stay a pure function of the
# component so that a module name never depends on what else was compiled.
_MODULE_COMPONENT_DIGEST_BYTES = 8


def _truncate_module_component(component: str) -> str:
    """Shorten one module-name component to fit the filesystem byte limit.

    The digest covers the full original component, so two components that
    share an over-long prefix still truncate to distinct results.
    """
    # An ASCII component's character count is its byte count, and str.isascii()
    # reads a flag cached on the string, so names that cannot exceed the limit
    # are cleared without encoding a copy of every component the compiler names.
    if component.isascii() and len(component) <= _MODULE_COMPONENT_BYTE_LIMIT:
        return component
    encoded = component.encode()
    if len(encoded) <= _MODULE_COMPONENT_BYTE_LIMIT:
        return component
    digest = hashlib.blake2b(encoded, digest_size=_MODULE_COMPONENT_DIGEST_BYTES)
    suffix = f"_{digest.hexdigest()}"
    prefix_byte_limit = _MODULE_COMPONENT_BYTE_LIMIT - len(suffix.encode())
    # Slicing bytes can split a multi-byte UTF-8 sequence; errors="ignore"
    # drops the resulting incomplete trailing bytes instead of raising.
    prefix = encoded[:prefix_byte_limit].decode("utf-8", errors="ignore")
    return prefix + suffix


@dataclass
class ClassReference:
    """A reference to a generated class, including its module location."""

    class_name: str
    module_name: str


def _authority_to_module_segment(name: str) -> str:
    """Convert an authority name segment to a valid Python module segment."""
    return name.translate(_AUTHORITY_CHAR_TABLE)


@typing.final
class NameAllocator:
    """Allocate unique names within one generated Python namespace."""

    def __init__(self, reserved: tuple[str, ...] = ()):
        """Initialize with names that generated members may not use."""
        self._used: set[str] = set(reserved)
        self._next_suffix: dict[str, int] = {}

    def allocate(self, candidate: str) -> str:
        """Return the first available name based on ``candidate``."""
        if candidate not in self._used:
            self._used.add(candidate)
            return candidate
        suffix = self._next_suffix.get(candidate, 2)
        while f"{candidate}_{suffix}" in self._used:
            suffix += 1
        name = f"{candidate}_{suffix}"
        self._used.add(name)
        self._next_suffix[candidate] = suffix + 1
        return name


def file_path_for_module(module_name: str) -> Path:
    """Convert a dotted module name to an __init__.py file path.

    Callers must obtain ``module_name`` from ``NameConverter``, which already
    truncates each component to the filesystem byte limit.
    """
    return Path(*module_name.split(".")) / "__init__.py"


# Names used at module scope in generated Python code.
_CLASS_EXTRA_RESERVED: frozenset[str] = frozenset(
    {
        "ClassVar",
        "literal",
        "main",
        "override",
    }
)


def _path_to_pascal(path: define_path.DefinePath) -> str:
    """Convert a definition path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )


def _is_reserved(name: str, extra: frozenset[str]) -> bool:
    return (
        keyword.iskeyword(name)
        or keyword.issoftkeyword(name)
        or name in _PYTHON_BUILTINS
        or name in extra
    )


def _make_unique(name: str, extra_reserved: frozenset[str], occupied: set[str]) -> str:
    """Append trailing underscores until the name is safe and unique."""
    while _is_reserved(name, extra_reserved) or name in occupied:
        name += "_"
    return name


class NameConverter:
    """Converts Define names to safe Python identifiers.

    A single instance is shared across an entire code generation run to ensure
    consistent naming (e.g., a class name used in a constraint list matches the
    class definition).
    """

    _class_names: dict[define_path.DefinePath, str]
    _execution_class_names: dict[define_path.DefinePath, str]
    _used_class_names: set[str]
    _authority_names: dict[str, str]
    _used_authority_names: set[str]

    def __init__(self):
        """Initialize with empty name caches."""
        self._class_names = {}
        self._execution_class_names = {}
        self._used_class_names = set()
        self._authority_names = {}
        self._used_authority_names = set()

    def class_name(self, path: define_path.DefinePath) -> str:
        """Convert a definition path to a safe PascalCase class name.

        Results are cached so the same path always returns the same name.
        """
        if path in self._class_names:
            return self._class_names[path]
        raw = _path_to_pascal(path)
        safe = _make_unique(raw, _CLASS_EXTRA_RESERVED, self._used_class_names)
        self._class_names[path] = safe
        self._used_class_names.add(safe)
        return safe

    def execution_class_name(self, path: define_path.DefinePath) -> str:
        """Return a unique class name for one action's generated execution state."""
        existing = self._execution_class_names.get(path)
        if existing is not None:
            return existing
        raw = self.class_name(path) + _EXECUTION_CLASS_SUFFIX
        safe = _make_unique(raw, _CLASS_EXTRA_RESERVED, self._used_class_names)
        self._execution_class_names[path] = safe
        self._used_class_names.add(safe)
        return safe

    def execution_class_reference(
        self, typed_global_name: ast.GlobalTypedNameReference
    ) -> ClassReference:
        """Build a reference to one generated action execution class."""
        action_class = self.class_reference(typed_global_name)
        return ClassReference(
            class_name=self.execution_class_name(
                typed_global_name.name_content.path.relative_path
            ),
            module_name=action_class.module_name,
        )

    def _guarantees_class_name(self, path: define_path.DefinePath) -> str:
        """Return a unique class name for one action's guarantee continuations."""
        raw = self.class_name(path) + _GUARANTEES_CLASS_SUFFIX
        safe = _make_unique(raw, _CLASS_EXTRA_RESERVED, self._used_class_names)
        self._used_class_names.add(safe)
        return safe

    def guarantees_class_reference(
        self, typed_global_name: ast.GlobalTypedNameInDefinition
    ) -> ClassReference:
        """Build a reference to one generated action guarantee class."""
        name_content = typed_global_name.name_content
        return ClassReference(
            class_name=self._guarantees_class_name(name_content.path.relative_path),
            module_name=self.module_name(name_content),
        )

    def authority_segment(self, authority: str) -> str:
        """Convert an authority string to a unique Python module segment.

        Results are cached so the same authority always returns the same name.
        Conflicts are resolved by appending underscores.
        """
        if authority in self._authority_names:
            return self._authority_names[authority]
        raw = _authority_to_module_segment(authority)
        safe = raw
        while safe in self._used_authority_names:
            safe += "_"
        self._authority_names[authority] = safe
        self._used_authority_names.add(safe)
        return safe

    def _module_name_parts(self, fqun: ast.Fqun, path: ast.GlobalPathName) -> list[str]:
        """Compute module name segments from an FQUN and definition path."""
        parts: list[str] = []
        if fqun.multiverse is not None:
            parts.append(fqun.multiverse.name)
        else:
            parts.append(constants.DEFAULT_MULTIVERSE)
        authority = typing.cast("ast.Authority", fqun.authority)
        parts.append(self.authority_segment(authority.name))
        parts.append(fqun.universe.name)
        parts.extend(path.relative_path.parts)
        return [_truncate_module_component(part) for part in parts]

    def module_name(self, name_content: ast.DefinitionGlobalNameContent) -> str:
        """Compute the dotted Python module name for a global definition."""
        parts = self._module_name_parts(name_content.fqun, name_content.path)
        return ".".join(parts)

    def constraints_to_class_references(
        self,
        constraints: ast.PositionConstraintBlock | None,
    ) -> list[ClassReference]:
        """Extract class references from a position constraint block."""
        if constraints is None:
            return []
        return [
            self.class_reference(requirement.typed_global_name)
            for requirement in constraints.requirements
        ]

    def implied_qualities_to_class_references(
        self,
        quality_implications: tuple[ast.QualityImplicationStatement, ...],
    ) -> list[ClassReference]:
        """Extract class references from a list of quality implication statements."""
        return [
            self.class_reference(implication.typed_global_name)
            for implication in quality_implications
        ]

    def class_reference(
        self, typed_global_name: ast.GlobalTypedNameReference
    ) -> ClassReference:
        """Build a reference to one generated global class."""
        name_content = typed_global_name.name_content
        cls_name = self.class_name(name_content.path.relative_path)
        fqun = name_content.fqun or typed_global_name.enclosing_fqun
        module_name = ".".join(self._module_name_parts(fqun, name_content.path))
        return ClassReference(class_name=cls_name, module_name=module_name)
