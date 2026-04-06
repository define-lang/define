# pyright: reportUnusedCallResult=false
"""Destroy dimension point statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_action_statements_block_with_destroy_dimension_point_local_position(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "run",
    ]


def test_action_statements_block_with_destroy_dimension_point_short_global_position(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/run",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_destroy_dimension_point_full_global_position(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/run",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_destroy_dimension_point_chained_position(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<to>::action</deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "to",
        "run",
    ]


def test_action_statements_block_with_destroy_dimension_point_short_global_chain(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/to",
        "/deposit",
        "/run",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_destroy_dimension_point_any_typed_chain(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/start",
        "/end",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "mid",
    ]


def test_action_statements_block_with_mixed_create_move_and_destroy_statements(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        create a dimension point in position<run>.\n"
        + "        move the dimension point in position<run> to position<done>.\n"
        + "        destroy the dimension point in position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "run",
        "run",
        "done",
        "done",
    ]


def test_action_statements_block_with_mixed_statements_and_multiple_destroy_dimension_points(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        destroy the dimension point in position<inner_pos>.\n"
        + "        destroy the dimension point in position</global_run>::action</deposit>::position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_run",
        "/deposit",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "inner_pos",
        "inner_pos",
        "inner_pos",
    ]


def test_action_statements_block_with_destroy_dimension_point_mixed_local_and_global(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "        destroy the dimension point in position<local_pos>::action</global_act>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_act",
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "local_pos",
        "inner",
    ]
