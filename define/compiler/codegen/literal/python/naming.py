"""Naming utilities for Python literal code generation."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast


def path_to_class_name(path: PurePosixPath) -> str:
    """Convert a definition path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )


def constraints_to_class_names(
    constraints: ast.PositionConstraintBlock | None,
) -> list[str]:
    """Extract PascalCase class names from a position constraint block."""
    if constraints is None:
        return []
    return [
        path_to_class_name(req.typed_global_name.name_content.path.relative_path)
        for req in constraints.requirements
    ]
