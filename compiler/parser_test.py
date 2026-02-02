"""Tests for the Define language parser."""

import lark
import pytest

from compiler import parser


@pytest.fixture
def p() -> parser.Parser:
    return parser.Parser()


def _get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    tokens = []
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

    def test_comment_with_trailing_whitespace(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("# comment with trailing space \n")
        assert exc_info.value.char == " "

    def test_same_line_comment_with_trailing_whitespace(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<standard:/path>. # comment \n")
        assert exc_info.value.char == " "


class TestStatementTerminators:
    def test_missing_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/path>\n")
        assert str(exc_info.value.token) == "\n"

    def test_missing_newline_after_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/path>.")
        assert str(exc_info.value.token) == ""

    def test_trailing_space_before_newline(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<standard:/path>. \n")
        assert exc_info.value.char == " "


class TestFileEncoding:
    def test_bom_at_start(self, p: parser.Parser) -> None:
        with pytest.raises(parser.ByteOrderMarkError):
            p.parse("\ufeffdefine the potential position<standard:/path>.\n")

    def test_crlf_line_endings(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<standard:/path>.\r\n")
        assert exc_info.value.char == "\r"


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
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/path.\n")
        assert str(exc_info.value.token) == "."

    def test_missing_open_angle(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential positionstandard:/path>.\n")
        assert str(exc_info.value.token) == "standard"

    def test_empty_name_content(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<>.\n")
        assert str(exc_info.value.token) == ">"

    def test_path_not_starting_with_slash(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:path>.\n")
        assert str(exc_info.value.token) == "standard"

    def test_empty_path_segment(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/a//b>.\n")
        assert str(exc_info.value.token) == "/"

    def test_local_name_not_valid_in_definitions(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<my_name>.\n")
        assert str(exc_info.value.token) == "my_name"


class TestMultiverseNameFormat:
    def test_uppercase_in_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<MyMv:example.com:my_lib:/path>.\n")
        assert exc_info.value.char == "M"

    def test_multiverse_starting_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<_mymv:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "_mymv"

    def test_multiverse_ending_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<mymv_:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "mymv_"

    def test_single_char_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<x:example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "x"

    def test_non_ascii_in_multiverse(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse(
                "define the potential position<m\u00fcv:example.com:my_lib:/path>.\n"
            )
        assert str(exc_info.value.token) == "m"


class TestAuthorityDomainFormat:
    def test_authority_domain_with_dots_and_hyphens(self, p: parser.Parser) -> None:
        tree = p.parse(
            "define the potential position<my-host.example.com:my_lib:/path>.\n"
        )
        assert _get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["my-host.example.com"]

    def test_uppercase_in_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<Example.Com:my_lib:/path>.\n")
        assert exc_info.value.char == "E"

    def test_authority_domain_starting_with_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<-example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-example.com"

    def test_authority_domain_ending_with_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com-:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "-"

    def test_authority_domain_starting_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<.example.com:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."

    def test_authority_domain_ending_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com.:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "."

    def test_single_char_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<x:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "x"

    def test_non_ascii_in_authority_domain(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<ex\u00e4mple.com:my_lib:/path>.\n")
        assert exc_info.value.char == "\u00e4"


class TestUniverseNameFormat:
    def test_universe_with_uppercase(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<example.com:MyLib:/path>.\n")
        assert _get_tokens_by_type(tree, "UNIVERSE_NAME") == ["MyLib"]

    def test_universe_starting_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com:_mylib:/path>.\n")
        assert str(exc_info.value.token) == "_mylib"

    def test_universe_ending_with_underscore(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com:mylib_:/path>.\n")
        assert str(exc_info.value.token) == "mylib_"

    def test_single_char_universe(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com:x:/path>.\n")
        assert str(exc_info.value.token) == "x"

    def test_non_ascii_in_universe(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com:m\u00fclib:/path>.\n")
        assert str(exc_info.value.token) == "m"


class TestPathSegmentFormat:
    def test_underscores_in_segments(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<my_mv:ex.com:my_lib:/a_b/c_d>.\n")
        assert _get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["a_b", "c_d"]

    def test_digits_in_path_segments(self, p: parser.Parser) -> None:
        tree = p.parse("define the potential position<standard:/item2>.\n")
        assert _get_tokens_by_type(tree, "PATH_SEGMENT") == ["item2"]

    def test_path_segment_starting_with_digit(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/2bad>.\n")
        assert str(exc_info.value.token) == "2bad"

    def test_invalid_chars_in_path_uppercase(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<standard:/BadName>.\n")
        assert exc_info.value.char == "B"

    def test_invalid_chars_in_path_hyphen(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/bad-name>.\n")
        assert str(exc_info.value.token) == "-name"

    def test_invalid_chars_in_path_dot(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/bad.name>.\n")
        assert str(exc_info.value.token) == "."

    def test_invalid_chars_in_path_tilde(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<standard:/bad~name>.\n")
        assert str(exc_info.value.token) == "~name"

    def test_invalid_chars_in_path_special(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<standard:/bad!name>.\n")
        assert exc_info.value.char == "!"


class TestAuthorityPathFormat:
    def test_invalid_chars_in_authority_path_uppercase(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedCharacters) as exc_info:
            p.parse("define the potential position<example.com/Bad:my_lib:/path>.\n")
        assert exc_info.value.char == "B"

    def test_invalid_chars_in_authority_path_angle(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential position<example.com/ba<d:my_lib:/path>.\n")
        assert str(exc_info.value.token) == "<"

    def test_authority_path_segment_starting_with_dot(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse(
                "define the potential position<example.com/.hidden:my_lib:/path>.\n"
            )
        assert str(exc_info.value.token) == "."


class TestIncompleteStatements:
    def test_multiple_spaces_between_keywords(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define  the potential position<standard:/path>.\n")
        assert str(exc_info.value.token) == "define"

    def test_define_the_potential_no_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential\n")
        assert str(exc_info.value.token) == "define"

    def test_define_the_potential_with_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the potential.\n")
        assert str(exc_info.value.token) == "define"

    def test_define_the_no_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the\n")
        assert str(exc_info.value.token) == "define"

    def test_define_the_with_terminator(self, p: parser.Parser) -> None:
        with pytest.raises(lark.exceptions.UnexpectedToken) as exc_info:
            p.parse("define the.\n")
        assert str(exc_info.value.token) == "define"
