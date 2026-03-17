"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import builtins
import keyword
import typing

if typing.TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast

_PYTHON_BUILTINS: frozenset[str] = frozenset(vars(builtins))

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

    def __init__(self):
        """Initialize with an empty class name cache."""
        self._class_names = {}
        self._used_class_names = set()

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

    def constraints_to_class_names(
        self,
        constraints: ast.PositionConstraintBlock | None,
    ) -> list[str]:
        """Extract safe PascalCase class names from a position constraint block."""
        if constraints is None:
            return []
        return [
            self.class_name(req.typed_global_name.name_content.path.relative_path)
            for req in constraints.requirements
        ]


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
