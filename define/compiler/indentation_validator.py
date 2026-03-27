"""Indentation validation for Define source files.

This is separate from the parser itself because Lark does not offer us a
reasonable way to be "lenient" while parsing but then spit out a bunch of
diagnostics about incorrect indentation. If we wrote our own parser, this
would probably just be part of the parser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, diagnostics

if TYPE_CHECKING:
    from pathlib import PurePosixPath


def _remove_comment(line: str) -> str:
    """Strip trailing comment respecting angle brackets."""
    inside_angles = False
    for i, ch in enumerate(line):
        if ch == "<":
            inside_angles = True
        elif ch == ">":
            inside_angles = False
        elif ch == "#" and not inside_angles:
            return line[:i].rstrip()
    return line


def validate_indentation(
    source: str,
    stop_before_line: int | None = None,
    file_path: PurePosixPath | None = None,
) -> list[diagnostics.Diagnostic]:
    """Validate indentation of Define source code.

    Returns diagnostics for incorrectly-indented lines.
    If stop_before_line is given, only checks lines before that line number
    (1-indexed).
    """
    lines = source.split("\n")
    result: list[diagnostics.Diagnostic] = []
    block_stack: list[int] = []

    for line_number, line in enumerate(lines, start=1):
        if stop_before_line is not None and line_number >= stop_before_line:
            break

        if not line.strip():
            continue

        actual_indent = len(line) - len(line.lstrip(" "))
        stripped = _remove_comment(line.strip())

        # In this block, we track actual_indent in the block_stack so that
        # we don't spam the developer with a hundred messages if they mis-indented
        # one line and then similarly indented all the next ones.
        if stripped.startswith("}"):
            if block_stack:
                expected = block_stack.pop()
                if actual_indent != expected:
                    result.append(
                        _make_diagnostic(
                            line_number, line, expected, actual_indent, file_path
                        )
                    )
            if stripped.endswith(" {"):
                block_stack.append(actual_indent)
        else:
            expected = block_stack[-1] + 4 if block_stack else 0
            if actual_indent != expected:
                result.append(
                    _make_diagnostic(
                        line_number, line, expected, actual_indent, file_path
                    )
                )
            if stripped and stripped.endswith(" {"):
                block_stack.append(actual_indent)

    return result


def _make_diagnostic(
    line_number: int,
    line: str,
    expected: int,
    actual: int,
    file_path: PurePosixPath | None = None,
) -> diagnostics.IncorrectIndentationDiagnostic:
    return diagnostics.IncorrectIndentationDiagnostic(
        location=ast.SourcePosition(
            line=line_number,
            column=1,
            end_line=line_number,
            end_column=len(line) + 1,
            file_path=file_path,
        ),
        expected_indent=expected,
        actual_indent=actual,
    )
