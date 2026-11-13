"""Writes the parser's Rust `LoadFailures`, which creates the load failures in `define.compiler.errors.syntax_errors`.

Each load failure class that the parser can report, which is every subclass of
`FileLoadFailureDiagnostic` in the module that is not itself a base class, gets
a `LoadFailures` method that takes the start and end positions of its location,
if it has one, then the rest of its fields.
"""

from __future__ import annotations

import pathlib
import sys

from define.compiler.errors import syntax_errors
from define.compiler.parsing.rust_generators import (
    diagnostic_description,
    rust_renderer,
)


def _load_failure_classes() -> list[type[syntax_errors.FileLoadFailureDiagnostic]]:
    namespace: dict[str, object] = dict(vars(syntax_errors))
    classes: list[type[syntax_errors.FileLoadFailureDiagnostic]] = []
    for value in namespace.values():
        if (
            isinstance(value, type)
            and issubclass(value, syntax_errors.FileLoadFailureDiagnostic)
            and value.__module__ == syntax_errors.__name__
            and not value.__subclasses__()
        ):
            classes.append(value)
    return classes


def main():
    """Write the Rust load failures to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = rust_renderer.LoadFailuresDescription(
        module_name=syntax_errors.__name__,
        load_failures=[
            diagnostic_description.describe_diagnostic(cls)
            for cls in _load_failure_classes()
        ],
    )
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_load_failures(description), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
