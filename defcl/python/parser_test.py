from pathlib import Path

import lark
import pytest

from defcl.python import parser

_TESTDATA_PATH = Path(__file__).parent.parent / "testdata"
_INVALID_PARSER_PATH = _TESTDATA_PATH / "invalid" / "parser"
_parser = parser.Parser()


def _get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    tokens = []
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
        tree = _parser.parse_file(_TESTDATA_PATH / "valid" / "empty_repeated.defcl")
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
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "booleans" / "false_literal.defcl"
            )

    def test_true_literal(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "booleans" / "true_literal.defcl")


class TestInvalidEnums:
    def test_lowercase_enum(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "enums" / "lowercase_enum.defcl")

    def test_mixed_case_enum(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "enums" / "mixed_case_enum.defcl")


class TestInvalidFieldNames:
    def test_double_underscore(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "field_names" / "double_underscore.defcl"
            )

    def test_hyphen(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "field_names" / "hyphen.defcl")

    def test_leading_digit(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "field_names" / "leading_digit.defcl"
            )

    def test_leading_underscore(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "field_names" / "leading_underscore.defcl"
            )

    def test_period(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "field_names" / "period.defcl")

    def test_trailing_underscore(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "field_names" / "trailing_underscore.defcl"
            )

    def test_underscore_digit(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "field_names" / "underscore_digit.defcl"
            )

    def test_uppercase(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "field_names" / "uppercase.defcl")


class TestInvalidFileFormat:
    def test_bom(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "file_format" / "bom.defcl")


class TestInvalidMessages:
    def test_angle_brackets(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "messages" / "angle_brackets.defcl"
            )


class TestInvalidNumbers:
    def test_hex(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "numbers" / "hex.defcl")

    def test_octal(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "numbers" / "octal.defcl")

    def test_scientific_int(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "scientific_int.defcl"
            )

    def test_scientific_float(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "scientific_float.defcl"
            )

    def test_leading_zeros(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "numbers" / "leading_zeros.defcl")

    def test_leading_decimal(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "leading_decimal.defcl"
            )

    def test_trailing_decimal(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "trailing_decimal.defcl"
            )

    def test_plus_sign(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "numbers" / "plus_sign.defcl")

    def test_space_after_sign(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "space_after_sign.defcl"
            )

    def test_type_suffix_f(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(_INVALID_PARSER_PATH / "numbers" / "type_suffix_f.defcl")

    def test_type_suffix_upper_f(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "numbers" / "type_suffix_upper_f.defcl"
            )


class TestInvalidSeparators:
    def test_comma_separator(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "separators" / "comma_separator.defcl"
            )

    def test_missing_colon(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "separators" / "missing_colon.defcl"
            )

    def test_semicolon(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "separators" / "semicolon.defcl")


class TestInvalidStrings:
    def test_raw_newline(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "strings" / "raw_newline.defcl")

    def test_single_quotes(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "strings" / "single_quotes.defcl")


class TestInvalidToplevel:
    def test_missing_toplevel_colon(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "toplevel" / "missing_toplevel_colon.defcl"
            )

    def test_scalar_toplevel(self):
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "toplevel" / "scalar_toplevel.defcl"
            )


class TestInvalidWhitespace:
    def test_carriage_return(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(
                _INVALID_PARSER_PATH / "whitespace" / "carriage_return.defcl"
            )

    def test_tab_char(self):
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse_file(_INVALID_PARSER_PATH / "whitespace" / "tab_char.defcl")
