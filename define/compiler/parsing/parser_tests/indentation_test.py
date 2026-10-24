# pyright: reportUnusedCallResult=false
"""Indentation diagnostic parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        ParseWithDiagnostics,
    )


def test_over_indented_quality_assignment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "          it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=10),
            expected_indent=8,
            actual_indent=10,
        )
    ]


def test_under_indented_quality_assignment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "      it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=6),
            expected_indent=8,
            actual_indent=6,
        )
    ]


def test_misindented_opener_does_not_move_its_block_contents(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "  it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
    ]


def test_under_indented_quality_assignment_block_close(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "  }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=2),
            expected_indent=4,
            actual_indent=2,
        )
    ]


def test_indented_definition_block_close(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + " }\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=1),
            expected_indent=0,
            actual_indent=1,
        )
    ]


def test_under_indented_comment_in_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "   # note\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=3),
            expected_indent=4,
            actual_indent=3,
        )
    ]


def test_unindented_comment_in_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "# note\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=1),
            expected_indent=4,
            actual_indent=0,
        )
    ]


def test_under_indented_non_ascii_comment_in_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "   # café\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=3),
            expected_indent=4,
            actual_indent=3,
        )
    ]


def test_indented_top_level_comment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "  # note\ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=1, column=1, end_line=1, end_column=2),
            expected_indent=0,
            actual_indent=2,
        )
    ]


def test_indentation_diagnostic_before_syntax_error(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "  it may only contain particles where {\n"
        + "      it has the position</child>\n"
        + "  }\n"
        + "}\n"
    )
    assert result.program is None
    assert isinstance(result.exception, parser_exceptions.MissingTerminator)
    assert result.exception.location == ast.SourceLocation(
        line=3, column=34, end_line=3, end_column=34
    )
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=6),
            expected_indent=8,
            actual_indent=6,
        ),
    ]


def test_action_statement_under_indented_after_blank_line(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "\n"
        + "it happens when {\n"
        + "}\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingTriggerConditionContent
    )
    assert result.exception.location == ast.SourceLocation(
        line=5, column=1, end_line=5, end_column=1
    )
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
    ]


def test_trigger_conditions_block_not_indented_in_action_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "it happens when {\n"
        + "    the position<run> has a particle.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=4),
            expected_indent=8,
            actual_indent=4,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
    ]


def test_trigger_conditions_block_under_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "  it happens when {\n"
        + "      the position<run> has a particle.\n"
        + "  } and it does {\n"
        + "  }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=6),
            expected_indent=8,
            actual_indent=6,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
    ]


def test_trigger_conditions_block_over_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "        it happens when {\n"
        + "            the position<run> has a particle.\n"
        + "        } and it does {\n"
        + "        }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=8),
            expected_indent=4,
            actual_indent=8,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=12),
            expected_indent=8,
            actual_indent=12,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=8),
            expected_indent=4,
            actual_indent=8,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=8),
            expected_indent=4,
            actual_indent=8,
        ),
    ]


def test_action_close_brace_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "    }\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=7, column=1, end_line=7, end_column=4),
            expected_indent=0,
            actual_indent=4,
        ),
    ]


def test_top_level_definition_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "    define the potential position<standard:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=1, column=1, end_line=1, end_column=4),
            expected_indent=0,
            actual_indent=4,
        ),
    ]


def test_comment_in_action_block_not_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + "# wrong indent comment\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
    ]


def test_indentation_wrong_in_several_definitions(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "  define the potential position<standard:/path>.\n"
        + "define the potential action<standard:/act> {\n"
        + "    define the position<run>.\n"
        + "  it happens when {\n"
        + "      the position<run> has a particle.\n"
        + "  } and it does {\n"
        + "  }\n"
        + "  }\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=1, column=1, end_line=1, end_column=2),
            expected_indent=0,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=6),
            expected_indent=8,
            actual_indent=6,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=7, column=1, end_line=7, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=8, column=1, end_line=8, end_column=2),
            expected_indent=0,
            actual_indent=2,
        ),
    ]


def test_action_lines_indented_at_random(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<standard:/path> {\n"
        + "    define the position<run>.\n"
        + " it happens when {\n"
        + "     the position<run> has a particle.\n"
        + "   } and it does {\n"
        + "     create a particle in position<run>.\n"
        + "       }\n"
        + "           }\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=1),
            expected_indent=4,
            actual_indent=1,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=5),
            expected_indent=8,
            actual_indent=5,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=3),
            expected_indent=4,
            actual_indent=3,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=5),
            expected_indent=8,
            actual_indent=5,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=7, column=1, end_line=7, end_column=7),
            expected_indent=4,
            actual_indent=7,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=8, column=1, end_line=8, end_column=11),
            expected_indent=0,
            actual_indent=11,
        ),
    ]


def test_every_line_of_shifted_definition_is_reported(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "  define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "      # a comment\n"
        + "      it may only contain particles where {\n"
        + "          it has the position</child>.\n"
        + "      }\n"
        + "  }\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=1, column=1, end_line=1, end_column=2),
            expected_indent=0,
            actual_indent=2,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=6),
            expected_indent=4,
            actual_indent=6,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=6),
            expected_indent=4,
            actual_indent=6,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=10),
            expected_indent=8,
            actual_indent=10,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=6),
            expected_indent=4,
            actual_indent=6,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=6, column=1, end_line=6, end_column=2),
            expected_indent=0,
            actual_indent=2,
        ),
    ]


def test_encoding_quality_assignment_under_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "  it has the encoding</decimal_text>.\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
    ]


def test_view_direction_statement_under_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "      it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=6),
            expected_indent=8,
            actual_indent=6,
        ),
    ]


def test_operation_argument_under_indented(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the operation</other> {\n"
        + "        with view<a> looking at view<left>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=8),
            expected_indent=12,
            actual_indent=8,
        ),
    ]
