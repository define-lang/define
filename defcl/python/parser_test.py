from pathlib import Path

import lark
import pytest

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"
_TESTDATA_PATH = Path(__file__).parent.parent / "testdata"
_INVALID_PARSER_PATH = _TESTDATA_PATH / "invalid" / "parser"
_parser = lark.Lark(_GRAMMAR_PATH.read_text(), parser="lalr", start="start")


def _get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    tokens = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            tokens.extend(_get_tokens_by_type(child, token_type))
        elif isinstance(child, lark.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens


class TestValidFiles:
    def test_single_toplevel(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "single_toplevel.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["project", "universe_name"]

    def test_multiple_toplevel(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "multiple_toplevel.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "universe_name",
            "settings",
            "log_level",
        ]

    def test_comments(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "comments.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "universe_name",
            "settings",
            "log_level",
        ]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_empty_message(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "empty_message.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["project"]

    def test_empty_repeated(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "empty_repeated.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == ["config", "tags", "items"]

    def test_enums(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "enums.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "ENUM_VALUE") == [
            "ACTIVE",
            "STATUS_ACTIVE",
            "V1",
            "LEVEL_2",
            "UNSPECIFIED",
        ]

    def test_field_names(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "field_names.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "config",
            "universe_name",
            "project_id",
            "retry_count",
            "field2name",
            "max_retries",
            "api_v2_endpoint",
        ]

    def test_floats(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "floats.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FLOAT") == [
            "3.14",
            "-2.0",
            "0.5",
            "123.456789",
        ]

    def test_integers(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "integers.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "INTEGER") == ["10", "-5", "0", "999999"]

    def test_repeated_scalars(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "repeated_scalars.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "STRING") == [
            '"tag1"',
            '"tag2"',
            '"tag3"',
        ]
        assert _get_tokens_by_type(tree, "INTEGER") == ["1", "2", "3"]
        assert _get_tokens_by_type(tree, "FLOAT") == ["1.5", "2.5"]
        assert _get_tokens_by_type(tree, "ENUM_VALUE") == ["ACTIVE", "INACTIVE"]

    def test_repeated_messages(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "repeated_messages.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "dependencies",
            "universe",
            "universe",
        ]

    def test_strings(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "strings.defcl").read_text()
        tree = _parser.parse(content)
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

    def test_whitespace(self) -> None:
        content = (_TESTDATA_PATH / "valid" / "whitespace.defcl").read_text()
        tree = _parser.parse(content)
        assert _get_tokens_by_type(tree, "FIELD_NAME") == [
            "project",
            "name",
            "settings",
            "level",
        ]


class TestInvalidBooleans:
    def test_false_literal(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "booleans" / "false_literal.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_true_literal(self) -> None:
        content = (_INVALID_PARSER_PATH / "booleans" / "true_literal.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)


class TestInvalidEnums:
    def test_lowercase_enum(self) -> None:
        content = (_INVALID_PARSER_PATH / "enums" / "lowercase_enum.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_mixed_case_enum(self) -> None:
        content = (_INVALID_PARSER_PATH / "enums" / "mixed_case_enum.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)


class TestInvalidFieldNames:
    def test_double_underscore(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "field_names" / "double_underscore.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_hyphen(self) -> None:
        content = (_INVALID_PARSER_PATH / "field_names" / "hyphen.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_leading_digit(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "field_names" / "leading_digit.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_leading_underscore(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "field_names" / "leading_underscore.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_period(self) -> None:
        content = (_INVALID_PARSER_PATH / "field_names" / "period.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_trailing_underscore(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "field_names" / "trailing_underscore.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_underscore_digit(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "field_names" / "underscore_digit.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_uppercase(self) -> None:
        content = (_INVALID_PARSER_PATH / "field_names" / "uppercase.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)


class TestInvalidFileFormat:
    def test_bom(self) -> None:
        content = (_INVALID_PARSER_PATH / "file_format" / "bom.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)


class TestInvalidMessages:
    def test_angle_brackets(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "messages" / "angle_brackets.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)


class TestInvalidNumbers:
    def test_hex(self) -> None:
        content = (_INVALID_PARSER_PATH / "numbers" / "hex.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_octal(self) -> None:
        content = (_INVALID_PARSER_PATH / "numbers" / "octal.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_scientific_int(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "scientific_int.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_scientific_float(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "scientific_float.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_leading_zeros(self) -> None:
        content = (_INVALID_PARSER_PATH / "numbers" / "leading_zeros.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_leading_decimal(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "leading_decimal.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_trailing_decimal(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "trailing_decimal.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_plus_sign(self) -> None:
        content = (_INVALID_PARSER_PATH / "numbers" / "plus_sign.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_space_after_sign(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "space_after_sign.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_type_suffix_f(self) -> None:
        content = (_INVALID_PARSER_PATH / "numbers" / "type_suffix_f.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_type_suffix_upper_f(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "numbers" / "type_suffix_upper_f.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)


class TestInvalidSeparators:
    def test_comma_separator(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "separators" / "comma_separator.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_missing_colon(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "separators" / "missing_colon.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_semicolon(self) -> None:
        content = (_INVALID_PARSER_PATH / "separators" / "semicolon.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)


class TestInvalidStrings:
    def test_raw_newline(self) -> None:
        content = (_INVALID_PARSER_PATH / "strings" / "raw_newline.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_single_quotes(self) -> None:
        content = (_INVALID_PARSER_PATH / "strings" / "single_quotes.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)


class TestInvalidToplevel:
    def test_missing_toplevel_colon(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "toplevel" / "missing_toplevel_colon.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)

    def test_scalar_toplevel(self) -> None:
        content = (
            _INVALID_PARSER_PATH / "toplevel" / "scalar_toplevel.defcl"
        ).read_text()
        with pytest.raises(lark.exceptions.UnexpectedToken):
            _parser.parse(content)


class TestInvalidWhitespace:
    def test_carriage_return(self) -> None:
        content = (
            (_INVALID_PARSER_PATH / "whitespace" / "carriage_return.defcl")
            .read_bytes()
            .decode("utf-8")
        )
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)

    def test_tab_char(self) -> None:
        content = (_INVALID_PARSER_PATH / "whitespace" / "tab_char.defcl").read_text()
        with pytest.raises(lark.exceptions.UnexpectedCharacters):
            _parser.parse(content)
