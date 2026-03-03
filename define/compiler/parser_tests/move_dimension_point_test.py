# pyright: reportUnusedCallResult=false
"""Move dimension point statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_action_statements_block_with_move_dimension_point_local_positions(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["source", "dest"]


def test_action_statements_block_with_move_dimension_point_short_global_positions(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/source",
        "/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_statements_block_with_move_dimension_point_full_global_positions(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<mv:define-lang.org:parser:/source> to position<mv:define-lang.org:parser:/dest>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/source",
        "mv:define-lang.org:parser:/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []


def test_action_statements_block_with_move_dimension_point_chained_source(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src>::action</deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "src",
        "inner",
        "dest",
    ]


def test_action_statements_block_with_move_dimension_point_chained_destination(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src> to position<dest>::action</deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "src",
        "dest",
        "inner",
    ]


def test_action_statements_block_with_move_dimension_point_both_chained(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<src>::action</a1> to position<dest>::action</a2>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/a1",
        "/a2",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["src", "dest"]


def test_action_statements_block_with_mixed_create_and_move_statements(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "        move the dimension point in position<run> to position<done>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "done",
    ]


def test_action_statements_block_with_move_dimension_point_mixed_local_and_global(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "        move the dimension point in position<local_src> to position</global_dest>.\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["local_src"]
