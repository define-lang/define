"""Compiles Jinja2 templates to Python modules for ModuleLoader."""

import sys
from pathlib import Path

from define.compiler.codegen.literal.python import template_env


def main() -> int:
    """Compile all Jinja2 templates in a directory to Python modules."""
    templates_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    env = template_env.create_environment(templates_dir)
    env.compile_templates(
        target=str(output_dir),
        filter_func=lambda name: name.endswith(".j2"),
        zip=None,
        ignore_errors=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
