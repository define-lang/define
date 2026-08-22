"""Shared Jinja2 Environment factory for Python code generation templates."""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING

from jinja2 import (
    Environment,
    FileSystemLoader,
    ModuleLoader,
    StrictUndefined,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def create_environment(
    templates_dir: Path,
    compiled_dir: Path | None = None,
    *,
    template_globals: Mapping[str, object] | None = None,
) -> Environment:
    """Create a Jinja2 Environment configured for Python code generation.

    Args:
        templates_dir: Directory containing .j2 template source files.
        compiled_dir: Optional directory containing pre-compiled template
            modules. When it exists, templates are loaded from those modules.
        template_globals: Values available to every template.
    """
    source_loader = FileSystemLoader(templates_dir)
    loader: FileSystemLoader | ModuleLoader
    if compiled_dir is not None and compiled_dir.is_dir():
        loader = ModuleLoader(compiled_dir)
    else:
        loader = source_loader
    environment = Environment(  # noqa: S701 - generating Python code, not HTML
        loader=loader,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    if template_globals is not None:
        typing.cast("dict[str, object]", environment.globals).update(template_globals)
    if isinstance(loader, ModuleLoader):
        # The compiler shares this environment among definition workers, so
        # finish the compiled loader's lazy imports while access is still serial.
        for template_name in source_loader.list_templates():
            if not template_name.endswith(".j2"):
                continue
            _ = environment.get_template(template_name)
    return environment
