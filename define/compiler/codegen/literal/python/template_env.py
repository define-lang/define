"""Shared Jinja2 Environment factory for Python code generation templates."""

from pathlib import Path

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    ModuleLoader,
    StrictUndefined,
)


def create_environment(
    templates_dir: Path,
    compiled_dir: Path | None = None,
) -> Environment:
    """Create a Jinja2 Environment configured for Python code generation.

    Args:
        templates_dir: Directory containing .j2 template source files.
        compiled_dir: Optional directory containing pre-compiled template
            modules. When provided, templates are loaded from compiled modules
            first, falling back to source files.
    """
    if compiled_dir is not None and compiled_dir.is_dir():
        loader: FileSystemLoader | ChoiceLoader = ChoiceLoader(
            [
                ModuleLoader(str(compiled_dir)),
                FileSystemLoader(str(templates_dir)),
            ]
        )
    else:
        loader = FileSystemLoader(str(templates_dir))
    return Environment(  # noqa: S701 - generating Python code, not HTML
        loader=loader,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
