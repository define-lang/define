# pyright: reportUnusedCallResult=false
# pyright: reportPrivateUsage=false

import pytest

from define.compiler import diagnostics, indentation_validator


class TestValidIndentation:
    def test_top_level_definition(self):
        source = "define the potential position<standard:/path>.\n"
        assert indentation_validator.validate_indentation(source) == []

    def test_action_with_4_space_block(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_nested_blocks(self):
        source = (
            "define the potential action<standard:/act> {\n"
            "    define the position<my_pos> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</child>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<my_pos> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_and_it_does_pattern(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<run>.\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_blank_lines_in_blocks(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "\n"
            "    } and it does {\n"
            "\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_comment_only_lines_at_correct_indent(self):
        source = (
            "# top-level comment\n"
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    # comment inside block\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_multiple_definitions(self):
        source = (
            "define the potential position<standard:/first>.\n"
            "define the potential position<standard:/second>.\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_position_with_constraints(self):
        source = (
            "define the potential position<standard:/path> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</child>.\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_comment_after_open_brace(self):
        source = (
            "define the potential action<standard:/path> { # comment\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []

    def test_comment_after_close_brace(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    } # comment\n"
            "}\n"
        )
        assert indentation_validator.validate_indentation(source) == []


class TestInvalidIndentation:
    def test_error_after_blank_line(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "\n"
            "it happens when {\n"
            "}\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        d0 = diags[0]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 4
        assert d0.position.column == 1
        assert d0.expected_indent == 4
        assert d0.actual_indent == 0

    def test_content_not_indented_in_block(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "it happens when {\n"
            "    the position<run> has a dimension point.\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        d0 = diags[0]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 3
        assert d0.position.column == 1
        assert d0.expected_indent == 4
        assert d0.actual_indent == 0

    def test_under_indented(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "  it happens when {\n"
            "      the position<run> has a dimension point.\n"
            "  } and it does {\n"
            "  }\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        d0 = diags[0]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 3
        assert d0.position.column == 1
        assert d0.expected_indent == 4
        assert d0.actual_indent == 2

    def test_over_indented(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "        it happens when {\n"
            "            the position<run> has a dimension point.\n"
            "        } and it does {\n"
            "        }\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        d0 = diags[0]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 3
        assert d0.position.column == 1
        assert d0.expected_indent == 4
        assert d0.actual_indent == 8

    def test_closing_brace_wrong_column(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "    }\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        diag = diags[0]
        assert isinstance(diag, diagnostics.IncorrectIndentationDiagnostic)
        assert diag.position.line == 7
        assert diag.position.column == 1
        assert diag.expected_indent == 0
        assert diag.actual_indent == 4

    def test_top_level_with_leading_whitespace(self):
        source = "    define the potential position<standard:/path>.\n"
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        diag = diags[0]
        assert isinstance(diag, diagnostics.IncorrectIndentationDiagnostic)
        assert diag.position.line == 1
        assert diag.position.column == 1
        assert diag.expected_indent == 0
        assert diag.actual_indent == 4

    def test_comment_only_line_wrong_indent(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "# wrong indent comment\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        diag = diags[0]
        assert isinstance(diag, diagnostics.IncorrectIndentationDiagnostic)
        assert diag.position.line == 3
        assert diag.position.column == 1
        assert diag.expected_indent == 4
        assert diag.actual_indent == 0

    def test_multiple_errors(self):
        source = (
            "  define the potential position<standard:/path>.\n"
            "define the potential action<standard:/act> {\n"
            "    define the position<run>.\n"
            "  it happens when {\n"
            "      the position<run> has a dimension point.\n"
            "  } and it does {\n"
            "  }\n"
            "  }\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 3
        d0 = diags[0]
        d1 = diags[1]
        d2 = diags[2]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d1, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d2, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 1
        assert d0.position.column == 1
        assert d0.expected_indent == 0
        assert d0.actual_indent == 2
        assert d1.position.line == 4
        assert d1.position.column == 1
        assert d1.expected_indent == 4
        assert d1.actual_indent == 2
        assert d2.position.line == 8
        assert d2.position.column == 1
        assert d2.expected_indent == 0
        assert d2.actual_indent == 2

    def test_randomly_indented_lines(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            " it happens when {\n"
            "     the position<run> has a dimension point.\n"
            "   } and it does {\n"
            "     create a dimension point in position<run>.\n"
            "       }\n"
            "           }\n"
        )
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 5
        d0 = diags[0]
        d1 = diags[1]
        d2 = diags[2]
        d3 = diags[3]
        d4 = diags[4]
        assert isinstance(d0, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d1, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d2, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d3, diagnostics.IncorrectIndentationDiagnostic)
        assert isinstance(d4, diagnostics.IncorrectIndentationDiagnostic)
        assert d0.position.line == 3
        assert d0.position.column == 1
        assert d0.expected_indent == 4
        assert d0.actual_indent == 1
        assert d1.position.line == 5
        assert d1.position.column == 1
        assert d1.expected_indent == 1
        assert d1.actual_indent == 3
        assert d2.position.line == 6
        assert d2.position.column == 1
        assert d2.expected_indent == 7
        assert d2.actual_indent == 5
        assert d3.position.line == 7
        assert d3.position.column == 1
        assert d3.expected_indent == 3
        assert d3.actual_indent == 7
        assert d4.position.line == 8
        assert d4.position.column == 1
        assert d4.expected_indent == 0
        assert d4.actual_indent == 11


class TestUpToLine:
    def test_stops_before_given_line(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "it happens when {\n"
            "    the position<run> has a dimension point.\n"
            "wrong indent\n"
            "}\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(source, stop_before_line=5)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.IncorrectIndentationDiagnostic)
        assert diags[0].position.line == 3

    def test_none_checks_all_lines(self):
        source = (
            "define the potential action<standard:/path> {\n"
            "    define the position<run>.\n"
            "it happens when {\n"
            "    the position<run> has a dimension point.\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = indentation_validator.validate_indentation(
            source, stop_before_line=None
        )
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.IncorrectIndentationDiagnostic)
        assert diags[0].position.line == 3


class TestRemoveComment:
    def test_strips_trailing_comment(self):
        assert indentation_validator._remove_comment("code # comment") == "code"

    def test_preserves_hash_in_angle_brackets(self):
        assert (
            indentation_validator._remove_comment("position<foo#bar>")
            == "position<foo#bar>"
        )

    def test_strips_comment_after_angle_brackets(self):
        assert (
            indentation_validator._remove_comment("position<foo> # comment")
            == "position<foo>"
        )

    def test_no_comment(self):
        assert indentation_validator._remove_comment("just code") == "just code"

    def test_comment_only(self):
        assert indentation_validator._remove_comment("# comment") == ""


class TestDiagnosticMessage:
    def test_message_format(self):
        source = "    define the potential position<standard:/path>.\n"
        diags = indentation_validator.validate_indentation(source)
        assert len(diags) == 1
        assert diags[0].message == (
            "expected 0 spaces of indentation on this line, but found 4"
        )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            (
                "define the potential action<standard:/act> {\n"
                "    define the position<my_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<my_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<my_pos>.\n"
                "    }\n"
                "}\n"
            ),
            id="deeply_nested",
        ),
        pytest.param(
            (
                "define the potential position<standard:/first>.\n"
                "define the potential action<standard:/second> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            id="mixed_definitions",
        ),
    ],
)
def test_valid_source_has_no_diagnostics(source: str):
    assert indentation_validator.validate_indentation(source) == []
