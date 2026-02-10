# pyright: reportUnusedCallResult=false
"""Tests for the Define language parser."""

from pathlib import Path

import lark
import pytest

from define.compiler import parser, parser_exceptions

_parser = parser.Parser()


@pytest.fixture
def p() -> parser.Parser:
    return _parser


def _get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    tokens: list[str] = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            tokens.extend(_get_tokens_by_type(child, token_type))
        elif isinstance(child, lark.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens


class TestComments:
    def test_comment_before_statement(self, p: parser.Parser) -> None:
        tree = p.parse(
            "# This is a comment\ndefine the potential position<standard:/path>.\n"
        )
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_comment_after_statement(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<standard:/path>.\n# Trailing comment\n"
        )
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_comment_on_same_line_as_statement(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/path>. # comment\n")
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_comment_on_same_line_multiple_spaces(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/path>.   # comment\n")
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_multiline_comments_with_blank_hash_line(self, p: parser.Parser) -> None:
        tree = p.parse(
            "# first line\n#\n# third line\ndefine the potential position<standard:/path>.\n"
        )
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]
        assert _get_tokens_by_type(tree, "COMMENT") == []

    def test_valid_syntax_in_comment_is_ignored(self, p: parser.Parser) -> None:
        tree = p.parse(
            "# define the potential position<standard:/ignored>.\n"
            + "define the potential position<standard:/actual>.\n"
        )
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["actual"]

    def test_control_character_in_comment(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
            p.parse(
                "# comment with\x01control char\n"
                + "define the potential position<standard:/path>.\n"
            )
        assert exc_info.value.char == "\x01"
        assert exc_info.value.column == 15

    def test_comment_with_trailing_whitespace(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
            p.parse("# comment with trailing space \n")
        assert exc_info.value.char == " "
        assert exc_info.value.column == 30

    def test_same_line_comment_with_trailing_whitespace(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
            p.parse("define the potential position<standard:/path>. # comment \n")
        assert exc_info.value.char == " "
        assert exc_info.value.column == 57

    def test_comment_only_file_without_newline(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.EmptyFileError) as exc_info:
            p.parse("# a comment")
        assert str(exc_info.value.token) == ""
        assert exc_info.value.column == 1


class TestStatementTerminators:
    def test_missing_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingTerminatorError) as exc_info:
            p.parse("define the potential position<standard:/path>\n")
        assert str(exc_info.value.token) == "\n"
        assert exc_info.value.column == 46

    def test_missing_newline_after_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingNewlineError) as exc_info:
            p.parse("define the potential position<standard:/path>.")
        assert str(exc_info.value.token) == ""
        assert exc_info.value.column == 46

    def test_trailing_space_before_newline(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
            p.parse("define the potential position<standard:/path>. \n")
        assert exc_info.value.char == " "
        assert exc_info.value.column == 47


class TestFileEncoding:
    def test_bom_at_start(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
            p.parse("\ufeffdefine the potential position<standard:/path>.\n")
        assert exc_info.value.char == "\ufeff"
        assert exc_info.value.column == 1

    def test_crlf_line_endings(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
            p.parse("define the potential position<standard:/path>.\r\n")
        assert exc_info.value.char == "\r"
        assert exc_info.value.column == 47

    def test_crlf_line_endings_in_comments(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
            p.parse("# a comment\r\n")
        assert exc_info.value.char == "\r"
        assert exc_info.value.column == 12

    def test_carriage_return_in_comment(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
            p.parse("# comment with\rcarriage return\n")
        assert exc_info.value.char == "\r"
        assert exc_info.value.column == 15

    def test_surrogate_character(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
            p.parse("define the potential position<standard:/path>.\n\udcff\n")
        assert exc_info.value.char == "\udcff"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 1


class TestActionDefinition:
    def test_action_definition_parses(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential action<standard:/path>.\n")
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["standard"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]


class TestMultipleDefinitions:
    def test_multiple_position_definitions(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<example.com:my_lib:/first>.\n"
            + "define the potential position<example.com:my_lib:/second>.\n"
        )
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
            "example.com",
            "example.com",
        ]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]

    def test_multiple_action_definitions(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential action<my_mv:example.com:my_lib:/first>.\n"
            + "define the potential action<my_mv:example.com:my_lib:/second>.\n"
        )
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv", "my_mv"]
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
            "example.com",
            "example.com",
        ]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]

    def test_mixed_position_and_action_definitions(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<example.com:my_lib:/pos>.\n"
            + "define the potential action<my_mv:example.com:my_lib:/act>.\n"
        )
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
            "example.com",
            "example.com",
        ]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["pos", "act"]

    def test_definitions_separated_by_blank_lines(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<standard:/first>.\n"
            + "\n"
            + "define the potential position<example.com:my_lib:/second>.\n"
        )
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["standard", "my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]

    def test_definitions_separated_by_comments(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<my_mv:example.com:my_lib:/first>.\n"
            + "# a comment between definitions\n"
            + "define the potential position<my_mv:example.com:my_lib:/second>.\n"
        )
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv", "my_mv"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]


class TestGlobalNameStructure:
    def test_full_fqun(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<my_mv:example.com:my_lib:/some/path>.\n"
        )
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]

    def test_authority_universe_no_multiverse(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<example.com:my_lib:/some/path>.\n"
        )
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == []
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]

    def test_standard_form(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/some/path>.\n")
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == []
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == []
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["standard"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]

    def test_authority_with_path(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<example.com/org/repo:my_lib:/foo>.\n"
        )
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
        assert _get_tokens_by_type(tree, "AUTHORITY_PATH_SEGMENT") == ["org", "repo"]
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["foo"]

    def test_multi_segment_global_path(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/a/b/c/d>.\n")
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["a", "b", "c", "d"]

    def test_missing_close_angle(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
            p.parse("define the potential position<standard:/path.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 45

    def test_missing_close_angle_in_three_part_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
            p.parse("define the potential position<example.com:my_lib:/path.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 55

    def test_missing_close_angle_in_full_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
            p.parse("define the potential position<mymv:example.com:my_lib:/path.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 60

    def test_missing_open_angle(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingOpenAngleBracketError) as exc_info:
            p.parse("define the potential positionstandard:/path>.\n")
        assert str(exc_info.value.token) == "standard"
        assert exc_info.value.column == 30

    def test_empty_name_content(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.EmptyNameError) as exc_info:
            p.parse("define the potential position<>.\n")
        assert str(exc_info.value.token) == ">"
        assert exc_info.value.column == 31

    def test_path_not_starting_with_slash(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:path>.\n")
        assert str(exc_info.value.token) == "standard"
        assert exc_info.value.column == 31

    def test_empty_path_segment(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:/a//b>.\n")
        assert str(exc_info.value.token) == "/"
        assert exc_info.value.column == 43

    def test_local_name_not_valid_in_definitions(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<my_name>.\n")
        assert str(exc_info.value.token) == "my_name"
        assert exc_info.value.column == 31


class TestMultiverseNameFormat:
    def test_uppercase_in_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
            p.parse("define the potential position<MyMv:example.com:my_lib:/path>.\n")
        assert exc_info.value.char == "M"
        assert exc_info.value.column == 31

    def test_multiverse_starting_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
            p.parse("define the potential position<_mymv:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "_mymv"
        assert exc_info.value.column == 31

    def test_multiverse_ending_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
            p.parse("define the potential position<mymv_:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "mymv_"
        assert exc_info.value.column == 31

    def test_single_char_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
            p.parse("define the potential position<x:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "x"
        assert exc_info.value.column == 31

    def test_non_ascii_in_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
            p.parse(
                "define the potential position<m\u00fcv:example.com:my_lib:/path>.\n"
            )
        assert str(exc_info.value.token) == "m"
        assert exc_info.value.column == 31


class TestAuthorityDomainFormat:
    def test_authority_domain_with_dots_and_hyphens(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<my-host.example.com:my_lib:/path>.\n"
        )
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["my-host.example.com"]

    def test_authority_domain_without_dot(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<localhost:my_lib:/path>.\n")
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["localhost"]

    def test_uppercase_in_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
            p.parse("define the potential position<Example.Com:my_lib:/path>.\n")
        assert exc_info.value.char == "E"
        assert exc_info.value.column == 31

    def test_authority_domain_starting_with_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<-example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-example.com"
        assert exc_info.value.column == 31

    def test_authority_domain_ending_with_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<example.com-:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-"
        assert exc_info.value.column == 42

    def test_authority_domain_starting_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<.example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 31

    def test_authority_domain_ending_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<example.com.:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 42

    def test_single_char_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<x:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "x"
        assert exc_info.value.column == 31

    def test_authority_domain_starting_with_dot_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<mymv:.example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 36

    def test_authority_domain_ending_with_dot_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<mymv:example.com.:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 47

    def test_authority_domain_starting_with_hyphen_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<mymv:-example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-example.com"
        assert exc_info.value.column == 36

    def test_authority_domain_ending_with_hyphen_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<mymv:example.com-:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-"
        assert exc_info.value.column == 47

    def test_single_char_authority_domain_in_full_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
            p.parse("define the potential position<mymv:a:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "a"
        assert exc_info.value.column == 36

    def test_non_ascii_in_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
            p.parse("define the potential position<ex\u00e4mple.com:my_lib:/path>.\n")
        assert exc_info.value.char == "\u00e4"
        assert exc_info.value.column == 33


class TestUniverseNameFormat:
    def test_universe_with_uppercase(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<example.com:MyLib:/path>.\n")
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["MyLib"]

    def test_universe_starting_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<example.com:_mylib:/path>.\n")
        assert str(exc_info.value.token) == "_mylib"
        assert exc_info.value.column == 43

    def test_universe_ending_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<example.com:mylib_:/path>.\n")
        assert str(exc_info.value.token) == "mylib_"
        assert exc_info.value.column == 43

    def test_single_char_universe(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<example.com:x:/path>.\n")
        assert str(exc_info.value.token) == "x"
        assert exc_info.value.column == 43

    def test_non_ascii_in_universe(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<example.com:m\u00fclib:/path>.\n")
        assert str(exc_info.value.token) == "m"
        assert exc_info.value.column == 43

    def test_universe_starting_with_underscore_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<mymv:example.com:_my_lib:/path>.\n")
        assert str(exc_info.value.token) == "_my_lib"
        assert exc_info.value.column == 48

    def test_universe_ending_with_underscore_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<mymv:example.com:my_lib_:/path>.\n")
        assert str(exc_info.value.token) == "my_lib_"
        assert exc_info.value.column == 48

    def test_single_char_universe_in_full_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
            p.parse("define the potential position<mymv:example.com:x:/path>.\n")
        assert str(exc_info.value.token) == "x"
        assert exc_info.value.column == 48


class TestPathSegmentFormat:
    def test_underscores_in_segments(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<my_mv:ex.com:my_lib:/a_b/c_d>.\n")
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["a_b", "c_d"]

    def test_digits_in_path_segments(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/item2>.\n")
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["item2"]

    def test_path_segment_starting_with_digit(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:/2bad>.\n")
        assert str(exc_info.value.token) == "2bad"
        assert exc_info.value.column == 41

    def test_invalid_chars_in_path_uppercase(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
            p.parse("define the potential position<standard:/BadName>.\n")
        assert exc_info.value.char == "B"
        assert exc_info.value.column == 41

    def test_invalid_chars_in_path_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:/bad-name>.\n")
        assert str(exc_info.value.token) == "-name"
        assert exc_info.value.column == 44

    def test_invalid_chars_in_path_dot(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:/bad.name>.\n")
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 44

    def test_invalid_chars_in_path_tilde(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<standard:/bad~name>.\n")
        assert str(exc_info.value.token) == "~name"
        assert exc_info.value.column == 44

    def test_invalid_chars_in_path_special(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
            p.parse("define the potential position<standard:/bad!name>.\n")
        assert exc_info.value.char == "!"
        assert exc_info.value.column == 44

    def test_invalid_chars_in_path_hyphen_in_three_part_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse("define the potential position<example.com:my_lib:/bad-name>.\n")
        assert str(exc_info.value.token) == "-name"
        assert exc_info.value.column == 54

    def test_invalid_chars_in_path_hyphen_in_full_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
            p.parse(
                "define the potential position<mymv:example.com:my_lib:/bad-name>.\n"
            )
        assert str(exc_info.value.token) == "-name"
        assert exc_info.value.column == 59

    def test_invalid_chars_in_path_special_in_three_part_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
            p.parse("define the potential position<example.com:my_lib:/bad!name>.\n")
        assert exc_info.value.char == "!"
        assert exc_info.value.column == 54

    def test_invalid_chars_in_path_special_in_full_fqun(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
            p.parse(
                "define the potential position<mymv:example.com:my_lib:/bad!name>.\n"
            )
        assert exc_info.value.char == "!"
        assert exc_info.value.column == 59


class TestAuthorityPathFormat:
    def test_invalid_chars_in_authority_path_uppercase(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
            p.parse("define the potential position<example.com/Bad:my_lib:/path>.\n")
        assert exc_info.value.char == "B"
        assert exc_info.value.column == 43

    def test_invalid_chars_in_authority_path_angle(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
            p.parse("define the potential position<example.com/ba<d:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "<"
        assert exc_info.value.column == 45

    def test_authority_path_segment_starting_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
            p.parse(
                "define the potential position<example.com/.hidden:my_lib:/path>.\n"
            )
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 43

    def test_authority_path_segment_starting_with_dot_in_full_fqun(
        self, p: parser.Parser
    ) -> None:
        with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
            p.parse(
                "define the potential position<mymv:example.com/.hidden:my_lib:/path>.\n"
            )
        assert str(exc_info.value.token) == "."
        assert exc_info.value.column == 48


class TestIncompleteStatements:
    def test_empty_file(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.EmptyFileError) as exc_info:
            p.parse("")
        assert str(exc_info.value.token) == ""
        assert exc_info.value.column == 1

    def test_file_all_spaces(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
            p.parse("   ")
        assert exc_info.value.char == " "
        assert exc_info.value.column == 1

    def test_file_spaces_and_newlines_only(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
            p.parse(" \n  \n ")
        assert exc_info.value.char == " "
        assert exc_info.value.column == 1

    def test_file_all_newlines(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.EmptyFileError) as exc_info:
            p.parse("\n\n\n")
        assert str(exc_info.value.token) == ""
        assert exc_info.value.column == 1

    def test_extra_space_after_define(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
            p.parse("define  the potential position<standard:/path>.\n")
        assert exc_info.value.column == 1

    def test_extra_space_after_the(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
            p.parse("define the  potential position<standard:/path>.\n")
        assert exc_info.value.column == 1

    def test_extra_space_after_potential(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
            p.parse("define the potential  position<standard:/path>.\n")
        assert exc_info.value.column == 1

    def test_extra_space_after_potential_action(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
            p.parse("define the potential  action<standard:/path>.\n")
        assert exc_info.value.column == 1

    def test_define_the_potential_no_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
            p.parse("define the potential\n")
        assert str(exc_info.value.token) == "define"
        assert exc_info.value.column == 1

    def test_define_the_potential_with_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
            p.parse("define the potential.\n")
        assert str(exc_info.value.token) == "define"
        assert exc_info.value.column == 1

    def test_define_the_no_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
            p.parse("define the\n")
        assert str(exc_info.value.token) == "define"
        assert exc_info.value.column == 1

    def test_define_the_with_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
            p.parse("define the.\n")
        assert str(exc_info.value.token) == "define"
        assert exc_info.value.column == 1


class TestParseFile:
    def test_parse_file(self, p: parser.Parser, tmp_path: Path):
        source = "define the potential position<standard:/path>.\n"
        file = tmp_path / "path.def"
        file.write_text(source, encoding="utf-8")
        tree, returned_source = p.parse_file(file)
        assert returned_source == source
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]

    def test_parse_file_preserves_crlf(self, p: parser.Parser, tmp_path: Path):
        source = "define the potential position<standard:/path>.\r\n"
        file = tmp_path / "path.def"
        file.write_bytes(source.encode("utf-8"))
        with pytest.raises(parser_exceptions.CarriageReturnError):
            _ = p.parse_file(file)

    def test_parse_file_includes_path_in_error(self, p: parser.Parser, tmp_path: Path):
        source = "define the potential position<standard:/path>.\r\n"
        file = tmp_path / "path.def"
        file.write_bytes(source.encode("utf-8"))
        with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
            _ = p.parse_file(file)
        assert str(file) in str(exc_info.value)


class TestErrorMessages:
    def test_error_message_without_path(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
            p.parse("\ufeffdefine the potential position<standard:/path>.\n")
        assert str(exc_info.value) == (
            "line 1, column 1\n"
            "\\ufeffdefine the potential position<standard:\n"
            "^\n"
            "Byte order mark not allowed: \\ufeff"
        )

    def test_error_message_with_path(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
            p.parse(
                "\ufeffdefine the potential position<standard:/path>.\n",
                file_path="test.def",
            )
        assert str(exc_info.value) == (
            'File "test.def", line 1, column 1\n'
            "\\ufeffdefine the potential position<standard:\n"
            "^\n"
            "Byte order mark not allowed: \\ufeff"
        )

    def test_char_error_message(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
            p.parse("define the potential position<standard:/path>.\r\n")
        assert str(exc_info.value) == (
            "line 1, column 47\n"
            " the potential position<standard:/path>.\\r\n"
            "                                        ^\n"
            "Carriage returns not allowed - use LF only: \\r"
        )

    def test_token_error_message(self, p: parser.Parser) -> None:
        with pytest.raises(parser_exceptions.MissingTerminatorError) as exc_info:
            p.parse("define the potential position<standard:/path>\n")
        assert str(exc_info.value) == (
            "line 1, column 46\n"
            "e the potential position<standard:/path>\n"
            "                                        ^\n"
            "Missing period at end of statement"
        )
