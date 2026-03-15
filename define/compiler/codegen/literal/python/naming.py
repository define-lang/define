"""Naming utilities for Python literal code generation."""

from pathlib import PurePosixPath


def path_to_class_name(path: PurePosixPath) -> str:
    """Convert a definition path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )
