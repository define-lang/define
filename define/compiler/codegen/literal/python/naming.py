"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import hashlib
import typing
from dataclasses import dataclass
from pathlib import Path

from define.compiler import ast, constants

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import define_path

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

    def __init__(self):
        """Initialize with no allocated names."""
        self._used: set[str] = set()
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


def _path_to_pascal(path: define_path.DefinePath) -> str:
    """Convert a definition path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )


class NameConverter:
    """Converts Define names to safe Python identifiers.

    A single instance is shared across an entire code generation run to ensure
    consistent naming (e.g., a class name used in a constraint list matches the
    class definition).
    """

    _class_names: dict[define_path.DefinePath, str]
    _class_references: dict[str, ClassReference]
    _execution_class_names: dict[define_path.DefinePath, str]
    _authority_names: dict[str, str]
    _used_authority_names: set[str]

    def __init__(self):
        """Initialize with empty name caches."""
        self._class_names = {}
        self._class_references = {}
        self._execution_class_names = {}
        self._authority_names = {}
        self._used_authority_names = set()

    def class_name(self, path: define_path.DefinePath) -> str:
        """Convert a definition path to a PascalCase class name.

        Results are cached so the same path always returns the same name.
        """
        if path in self._class_names:
            return self._class_names[path]
        name = _path_to_pascal(path)
        self._class_names[path] = name
        return name

    def execution_class_name(self, path: define_path.DefinePath) -> str:
        """Return the class name for one action's generated execution state."""
        existing = self._execution_class_names.get(path)
        if existing is not None:
            return existing
        name = self.class_name(path) + _EXECUTION_CLASS_SUFFIX
        self._execution_class_names[path] = name
        return name

    def execution_class_reference(
        self, typed_global_name: ast.GlobalTypedName
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
        """Return the class name for one action's guarantee continuations."""
        return self.class_name(path) + _GUARANTEES_CLASS_SUFFIX

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

    def class_reference(self, typed_global_name: ast.GlobalTypedName) -> ClassReference:
        """Build a reference to one generated global class."""
        canonical_name = typed_global_name.full_typed_name
        existing = self._class_references.get(canonical_name)
        if existing is not None:
            return existing
        name_content = typed_global_name.name_content
        cls_name = self.class_name(name_content.path.relative_path)
        if isinstance(typed_global_name, ast.GlobalTypedNameReference):
            fqun = typed_global_name.effective_fqun
        else:
            fqun = typing.cast("ast.DefinitionGlobalNameContent", name_content).fqun
        module_name = ".".join(self._module_name_parts(fqun, name_content.path))
        class_reference = ClassReference(class_name=cls_name, module_name=module_name)
        self._class_references[canonical_name] = class_reference
        return class_reference
