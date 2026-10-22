"""Writes the parser's Rust `SyntaxErrors`, which creates the exceptions in `define.compiler.errors.parser_exceptions`.

Each exception class that the parser can raise, which is every subclass of
`DefineSyntaxError` that is not itself a base class, gets a `SyntaxErrors`
method that takes the start and end positions of its location, then the rest
of its constructor's parameters, which are all strings.
"""

from __future__ import annotations

import inspect
import pathlib
import sys
import typing

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.native.rust_generators import rust_names, rust_renderer


def _exception_classes() -> list[type[parser_exceptions.DefineSyntaxError]]:
    namespace: dict[str, object] = dict(vars(parser_exceptions))
    classes: list[type[parser_exceptions.DefineSyntaxError]] = []
    for value in namespace.values():
        if (
            isinstance(value, type)
            and issubclass(value, parser_exceptions.DefineSyntaxError)
            and value.__module__ == parser_exceptions.__name__
            and not value.__subclasses__()
        ):
            classes.append(value)
    return classes


def _describe_exception(cls: type) -> rust_renderer.ParserException:
    location, *text_parameters = inspect.signature(cls).parameters.values()
    # The annotations are strings because parser_exceptions postpones their
    # evaluation.
    location_annotation = typing.cast("object", location.annotation)
    if location.name != "location" or location_annotation != "ast.SourceLocation":
        raise ValueError(f"{cls.__name__} must take a location first")
    for parameter in text_parameters:
        annotation = typing.cast("object", parameter.annotation)
        if annotation != "str":
            raise ValueError(
                f"{cls.__name__}.{parameter.name} must be a str, not {annotation}"
            )
    return rust_renderer.ParserException(
        name=cls.__name__,
        snake_case_name=rust_names.snake_case_name(cls.__name__),
        text_parameters=[parameter.name for parameter in text_parameters],
    )


def main():
    """Write the Rust syntax errors to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = rust_renderer.SyntaxErrorsDescription(
        module_name=parser_exceptions.__name__,
        exceptions=[_describe_exception(cls) for cls in _exception_classes()],
    )
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_syntax_errors(description), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
