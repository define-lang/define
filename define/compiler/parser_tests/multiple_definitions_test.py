# pyright: reportUnusedCallResult=false
"""Multiple definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_multiple_position_definitions(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<example.com:my_lib:/first>.\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
        "example.com",
        "example.com",
    ]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]


def test_multiple_action_definitions(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<my_mv:example.com:my_lib:/first>.\n"
        + "define the potential action<my_mv:example.com:my_lib:/second>.\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv", "my_mv"]
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
        "example.com",
        "example.com",
    ]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]


def test_mixed_position_and_action_definitions(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<example.com:my_lib:/pos>.\n"
        + "define the potential action<my_mv:example.com:my_lib:/act>.\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
        "example.com",
        "example.com",
    ]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib", "my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["pos", "act"]


def test_definitions_separated_by_blank_lines(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<standard:/first>.\n"
        + "\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["standard", "my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]


def test_definitions_separated_by_comments(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<my_mv:example.com:my_lib:/first>.\n"
        + "# a comment between definitions\n"
        + "define the potential position<my_mv:example.com:my_lib:/second>.\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv", "my_mv"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["first", "second"]
