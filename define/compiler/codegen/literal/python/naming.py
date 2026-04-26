"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import builtins
import keyword
import typing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from define.compiler import constants

if typing.TYPE_CHECKING:
    from define.compiler import ast

_PYTHON_BUILTINS: frozenset[str] = frozenset(vars(builtins))

_AUTHORITY_CHAR_TABLE = str.maketrans(".-~/", "____")


@dataclass
class ClassReference:
    """A reference to a generated class, including its module location."""

    class_name: str
    module_name: str


def _authority_to_module_segment(name: str) -> str:
    """Convert an authority name segment to a valid Python module segment."""
    return name.translate(_AUTHORITY_CHAR_TABLE)


def file_path_for_module(module_name: str) -> Path:
    """Convert a dotted module name to an __init__.py file path."""
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

# Names used inside method bodies in generated Python code.
_LOCAL_VAR_EXTRA_RESERVED: frozenset[str] = frozenset(
    {
        "literal",
        "self",
    }
)


def _path_to_pascal(path: PurePosixPath) -> str:
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

    _class_names: dict[PurePosixPath, str]
    _used_class_names: set[str]
    _authority_names: dict[str, str]
    _used_authority_names: set[str]

    def __init__(self):
        """Initialize with empty name caches."""
        self._class_names = {}
        self._used_class_names = set()
        self._authority_names = {}
        self._used_authority_names = set()

    def class_name(self, path: PurePosixPath) -> str:
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
        if fqun.authority is not None:
            parts.append(self.authority_segment(fqun.authority.name))
        parts.append(fqun.universe.name)
        parts.extend(path.relative_path.parts)
        return parts

    def module_name(self, name_content: ast.GlobalNameContent) -> str:
        """Compute the dotted Python module name for a global name.

        The name_content must have a non-None fqun.
        """
        fqun = name_content.fqun
        if fqun is None:
            raise ValueError("name_content.fqun must not be None")
        parts = self._module_name_parts(fqun, name_content.path)
        return ".".join(parts)

    def constraints_to_class_references(
        self,
        constraints: ast.PositionConstraintBlock | None,
        enclosing_fqun: ast.Fqun,
    ) -> list[ClassReference]:
        """Extract class references from a position constraint block."""
        if constraints is None:
            return []
        return [
            self._build_class_reference(requirement.typed_global_name, enclosing_fqun)
            for requirement in constraints.requirements
        ]

    def quality_requirements_to_class_references(
        self,
        quality_requirements: list[ast.QualityRequirementStatement],
        enclosing_fqun: ast.Fqun,
    ) -> list[ClassReference]:
        """Extract class references from a list of quality requirement statements."""
        return [
            self._build_class_reference(requirement.typed_global_name, enclosing_fqun)
            for requirement in quality_requirements
        ]

    def _build_class_reference(
        self,
        typed_global_name: ast.GlobalTypedNameReference,
        enclosing_fqun: ast.Fqun,
    ) -> ClassReference:
        name_content = typed_global_name.name_content
        cls_name = self.class_name(name_content.path.relative_path)
        fqun = name_content.fqun or enclosing_fqun
        module_name = ".".join(self._module_name_parts(fqun, name_content.path))
        return ClassReference(class_name=cls_name, module_name=module_name)


class LocalNameConverter:
    """Converts local variable names to safe Python identifiers within one scope.

    Names are converted on the fly; each converted name is tracked so that
    later names that collide with earlier mangled names get further mangled.
    """

    _names: dict[str, str]
    _used: set[str]

    def __init__(self):
        """Initialize with an empty name mapping."""
        self._names = {}
        self._used = set()

    def convert(self, name: str) -> str:
        """Convert a local variable name to a safe Python identifier."""
        if name in self._names:
            return self._names[name]
        safe = _make_unique(name, _LOCAL_VAR_EXTRA_RESERVED, self._used)
        self._names[name] = safe
        self._used.add(safe)
        return safe
