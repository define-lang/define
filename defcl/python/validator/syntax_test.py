# pyright: reportUnusedCallResult=false
from pathlib import Path

import lark
import pytest

from defcl.python import exceptions
from defcl.python.validator import syntax

_TESTDATA_PATH = Path(__file__).parent.parent.parent / "testdata"
_INVALID_SYNTAX_PATH = _TESTDATA_PATH / "invalid" / "syntax"
_parser = syntax.Parser()


def _get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    tokens: list[str] = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            tokens.extend(_get_tokens_by_type(child, token_type))
        elif isinstance(child, lark.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens


class TestValidFiles:
    def test_single_toplevel(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "single_toplevel.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["project", "universe_name"]

    def test_multiple_toplevel(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "multiple_toplevel.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "universe_name",
            "settings",
            "log_level",
        ]

    def test_comments(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "comments.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "universe_name",
            "settings",
            "log_level",
        ]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_empty_message(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "empty_message.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["project"]

    def test_empty_repeated(self):
        tree = _parser.parse_file(
            _TESTDATA_PATH / "valid" / "empty_repeated_scalars.defcl"
        )
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["config", "tags", "items"]

    def test_enums(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "enums.defcl")
        assert _get_tokens_by_type(tree, "ENUM_VALUE") == [
            "ACTIVE",
            "STATUS_ACTIVE",
            "V1",
            "LEVEL_2",
            "UNSPECIFIED",
        ]

    def test_field_names(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "field_names.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "config",
            "universe_name",
            "project_id",
            "retry_count",
            "field2name",
            "max_retries",
            "api_v2_endpoint",
        ]

    def test_floats(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "floats.defcl")
        assert _get_tokens_by_type(tree, "FLOAT") == [
            "3.14",
            "-2.0",
            "0.5",
            "123.456789",
        ]

    def test_integers(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "integers.defcl")
        assert _get_tokens_by_type(tree, "INTEGER") == ["10", "-5", "0", "999999"]

    def test_repeated_scalars(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "repeated_scalars.defcl")
        assert _get_tokens_by_type(tree, "STRING") == [
            '"tag1"',
            '"tag2"',
            '"tag3"',
        ]
        assert _get_tokens_by_type(tree, "INTEGER") == ["1", "2", "3"]
        assert _get_tokens_by_type(tree, "FLOAT") == ["1.5", "2.5"]
        assert _get_tokens_by_type(tree, "ENUM_VALUE") == ["ACTIVE", "INACTIVE"]

    def test_nested_messages(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "nested_messages.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "name",
            "database",
            "host",
            "port",
            "pool",
            "max_connections",
        ]

    def test_repeated_messages(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "repeated_messages.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "dependencies",
            "universe",
            "universe",
        ]

    def test_strings(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "strings.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "config",
            "basic",
            "with_spaces",
            "with_newline",
            "with_tab",
            "with_backslash",
            "with_quote",
            "with_apostrophe",
            "with_bell",
            "with_backspace",
            "with_formfeed",
            "with_return",
            "with_vtab",
            "with_question",
            "octal_escape",
            "hex_escape",
            "unicode_bmp",
            "unicode_smp",
            "unicode_spb",
        ]

    def test_whitespace(self):
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "whitespace.defcl")
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "name",
            "settings",
            "level",
        ]


class TestInvalidBooleans:
    def test_false_literal(self):
        with pytest.raises(exceptions.BooleanNotSupportedError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "booleans" / "false_literal.defcl"
            )
        assert exc_info.value.token.type == "FIELD_NAME"
        assert str(exc_info.value.token) == "false"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 14

    def test_true_literal(self):
        with pytest.raises(exceptions.BooleanNotSupportedError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "booleans" / "true_literal.defcl")
        assert exc_info.value.token.type == "FIELD_NAME"
        assert str(exc_info.value.token) == "true"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 14


class TestInvalidEnums:
    def test_lowercase_enum(self):
        with pytest.raises(exceptions.InvalidEnumCaseError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "enums" / "lowercase_enum.defcl")
        assert exc_info.value.token.type == "FIELD_NAME"
        assert str(exc_info.value.token) == "active"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13

    def test_mixed_case_enum(self):
        with pytest.raises(exceptions.InvalidEnumCaseError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "enums" / "mixed_case_enum.defcl")
        assert exc_info.value.token.type == "RBRACE"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 1


class TestInvalidFieldNames:
    def test_double_underscore(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "field_names" / "double_underscore.defcl"
            )
        assert exc_info.value.char == "_"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 11

    def test_hyphen(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "field_names" / "hyphen.defcl")
        assert exc_info.value.char == "-"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13

    def test_leading_digit(self):
        with pytest.raises(exceptions.InvalidFieldNameTokenError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "field_names" / "leading_digit.defcl"
            )
        assert exc_info.value.token.type == "INTEGER"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5

    def test_leading_underscore(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "field_names" / "leading_underscore.defcl"
            )
        assert exc_info.value.char == "_"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5

    def test_period(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "field_names" / "period.defcl")
        assert exc_info.value.char == "."
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13

    def test_trailing_underscore(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "field_names" / "trailing_underscore.defcl"
            )
        assert exc_info.value.char == "_"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 18

    def test_underscore_digit(self):
        with pytest.raises(exceptions.InvalidFieldNameError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "field_names" / "underscore_digit.defcl"
            )
        assert exc_info.value.char == "_"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 11

    def test_uppercase(self):
        with pytest.raises(exceptions.InvalidFieldNameTokenError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "field_names" / "uppercase.defcl")
        assert exc_info.value.token.type == "ENUM_VALUE"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5


class TestInvalidFileFormat:
    def test_bom(self):
        with pytest.raises(exceptions.ByteOrderMarkError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "file_format" / "bom.defcl")
        assert exc_info.value.char == "\ufeff"
        assert exc_info.value.line == 1
        assert exc_info.value.column == 1

    def test_no_trailing_newline(self):
        with pytest.raises(exceptions.MissingTrailingNewlineError):
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "file_format" / "no_trailing_newline.defcl"
            )


class TestInvalidMessages:
    def test_angle_brackets(self):
        with pytest.raises(exceptions.AngleBracketsNotAllowedError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "messages" / "angle_brackets.defcl"
            )
        assert exc_info.value.char == "<"
        assert exc_info.value.line == 1
        assert exc_info.value.column == 10

    def test_nested_angle_brackets(self):
        with pytest.raises(exceptions.AngleBracketsNotAllowedError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "messages" / "nested_angle_brackets.defcl"
            )
        assert exc_info.value.char == "<"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13


class TestInvalidNumbers:
    def test_hex(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "numbers" / "hex.defcl")
        assert exc_info.value.token.type == "ENUM_VALUE"
        assert str(exc_info.value.token) == "A"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 15

    def test_octal(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "numbers" / "octal.defcl")
        assert exc_info.value.token.type == "INTEGER"
        assert str(exc_info.value.token) == "777"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13

    def test_scientific_int(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "scientific_int.defcl"
            )
        assert exc_info.value.token.type == "RBRACE"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 1

    def test_scientific_float(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "scientific_float.defcl"
            )
        assert exc_info.value.token.type == "INTEGER"
        assert str(exc_info.value.token) == "-2"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 16

    def test_leading_zeros(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "numbers" / "leading_zeros.defcl")
        assert exc_info.value.token.type == "INTEGER"
        assert str(exc_info.value.token) == "0"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 13

    def test_leading_decimal(self):
        with pytest.raises(exceptions.InvalidNumberFormatCharError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "leading_decimal.defcl"
            )
        assert exc_info.value.char == "."
        assert exc_info.value.line == 2
        assert exc_info.value.column == 12

    def test_trailing_decimal(self):
        with pytest.raises(exceptions.InvalidNumberFormatCharError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "trailing_decimal.defcl"
            )
        assert exc_info.value.char == "."
        assert exc_info.value.line == 2
        assert exc_info.value.column == 14

    def test_plus_sign(self):
        with pytest.raises(exceptions.InvalidNumberFormatCharError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "numbers" / "plus_sign.defcl")
        assert exc_info.value.char == "+"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 12

    def test_space_after_sign(self):
        with pytest.raises(exceptions.InvalidNumberFormatCharError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "space_after_sign.defcl"
            )
        assert exc_info.value.char == "-"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 12

    def test_type_suffix_f(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "numbers" / "type_suffix_f.defcl")
        assert exc_info.value.token.type == "RBRACE"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 1

    def test_type_suffix_upper_f(self):
        with pytest.raises(exceptions.InvalidNumberFormatError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "numbers" / "type_suffix_upper_f.defcl"
            )
        assert exc_info.value.token.type == "ENUM_VALUE"
        assert str(exc_info.value.token) == "F"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 14


class TestInvalidSeparators:
    def test_comma_separator(self):
        with pytest.raises(exceptions.InvalidSeparatorError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "separators" / "comma_separator.defcl"
            )
        assert exc_info.value.token.type == "COMMA"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 9

    def test_missing_colon(self):
        with pytest.raises(exceptions.MissingColonError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "separators" / "missing_colon.defcl"
            )
        assert exc_info.value.token.type == "STRING"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 11

    def test_semicolon(self):
        with pytest.raises(exceptions.InvalidSeparatorCharError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "separators" / "semicolon.defcl")
        assert exc_info.value.char == ";"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 18


class TestInvalidStrings:
    def test_raw_newline(self):
        with pytest.raises(exceptions.UnterminatedStringError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "strings" / "raw_newline.defcl")
        assert exc_info.value.char == '"'
        assert exc_info.value.line == 2
        assert exc_info.value.column == 12

    def test_single_quotes(self):
        with pytest.raises(exceptions.SingleQuotesNotAllowedError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "strings" / "single_quotes.defcl")
        assert exc_info.value.char == "'"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 12


class TestInvalidToplevel:
    def test_missing_toplevel_colon(self):
        with pytest.raises(exceptions.MissingColonError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "toplevel" / "missing_toplevel_colon.defcl"
            )
        assert exc_info.value.token.type == "LBRACE"
        assert exc_info.value.line == 1
        assert exc_info.value.column == 9

    def test_scalar_toplevel(self):
        with pytest.raises(exceptions.ScalarAtToplevelError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "toplevel" / "scalar_toplevel.defcl"
            )
        assert exc_info.value.token.type == "STRING"
        assert exc_info.value.line == 1
        assert exc_info.value.column == 7


class TestInvalidWhitespace:
    def test_carriage_return(self):
        with pytest.raises(exceptions.CarriageReturnNotAllowedError) as exc_info:
            _parser.parse_file(
                _INVALID_SYNTAX_PATH / "whitespace" / "carriage_return.defcl"
            )
        assert exc_info.value.char == "\r"
        assert exc_info.value.line == 1
        assert exc_info.value.column == 10

    def test_tab_char(self):
        with pytest.raises(exceptions.TabNotAllowedError) as exc_info:
            _parser.parse_file(_INVALID_SYNTAX_PATH / "whitespace" / "tab_char.defcl")
        assert exc_info.value.char == "\t"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 1


class TestErrorMessages:
    def test_token_error_with_path(self):
        path = _INVALID_SYNTAX_PATH / "booleans" / "false_literal.defcl"
        with pytest.raises(exceptions.BooleanNotSupportedError) as exc_info:
            _parser.parse_file(path)
        assert str(exc_info.value) == (
            f'File "{path}", line 2, column 14\n'
            "    enabled: false\n"
            "             ^\n"
            "Boolean literals not supported - use enums instead"
        )

    def test_char_error_with_path(self):
        path = _INVALID_SYNTAX_PATH / "whitespace" / "tab_char.defcl"
        with pytest.raises(exceptions.TabNotAllowedError) as exc_info:
            _parser.parse_file(path)
        assert str(exc_info.value) == (
            f'File "{path}", line 2, column 1\n'
            '\tvalue: "test"\n'
            "^\n"
            "Tabs not allowed - use spaces"
        )

    def test_error_without_path(self):
        with pytest.raises(exceptions.BooleanNotSupportedError) as exc_info:
            _parser.parse("config: {\n    enabled: false\n}\n")
        assert str(exc_info.value) == (
            "line 2, column 14\n"
            "    enabled: false\n"
            "             ^\n"
            "Boolean literals not supported - use enums instead"
        )

    def test_missing_trailing_newline_with_path(self):
        path = _INVALID_SYNTAX_PATH / "file_format" / "no_trailing_newline.defcl"
        with pytest.raises(exceptions.MissingTrailingNewlineError) as exc_info:
            _parser.parse_file(path)
        assert str(exc_info.value) == (
            f'File "{path}"\nFile does not end with a newline'
        )

    def test_missing_trailing_newline_without_path(self):
        with pytest.raises(exceptions.MissingTrailingNewlineError) as exc_info:
            _parser.parse('project: {\n    name: "test"\n}')
        assert str(exc_info.value) == "File does not end with a newline"
