# pyright: reportUnusedCallResult=false
"""Multiple definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_multiple_position_definitions(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<example.com:my_lib:/first>.\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "example.com:my_lib:/first",
        "example.com:my_lib:/second",
    ]


def test_multiple_action_definitions(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<my_mv:example.com:my_lib:/first> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential action<my_mv:example.com:my_lib:/second> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "my_mv:example.com:my_lib:/first",
        "my_mv:example.com:my_lib:/second",
    ]


def test_mixed_position_and_action_definitions(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<example.com:my_lib:/pos>.\n"
        + "define the potential action<my_mv:example.com:my_lib:/act> {\n"
        + "    define the position<_noop>.\n"
        + "    it happens when {\n"
        + "        the position<_noop> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<__noop>.\n"
        + "        create a dimension point in position<__noop>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "example.com:my_lib:/pos",
        "my_mv:example.com:my_lib:/act",
    ]


def test_definitions_separated_by_blank_lines(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/first>.\n"
        + "\n"
        + "define the potential position<example.com:my_lib:/second>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/first",
        "example.com:my_lib:/second",
    ]


def test_definitions_separated_by_comments(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<my_mv:example.com:my_lib:/first>.\n"
        + "# a comment between definitions\n"
        + "define the potential position<my_mv:example.com:my_lib:/second>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "my_mv:example.com:my_lib:/first",
        "my_mv:example.com:my_lib:/second",
    ]
