# pyright: reportUnusedCallResult=false
"""Move particle statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_action_statements_block_with_move_particle_local_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "source",
        "dest",
    ]


def test_action_statements_block_with_move_particle_short_global_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/source",
        "/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_move_particle_full_global_positions(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<mv:define-lang.org:parser:/source> to position<mv:define-lang.org:parser:/dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/source",
        "mv:define-lang.org:parser:/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_move_particle_chained_source(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src>::action</deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "inner",
        "dest",
    ]


def test_action_statements_block_with_move_particle_chained_destination(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src> to position<dest>::action</deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "dest",
        "inner",
    ]


def test_action_statements_block_with_move_particle_both_chained(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<src>::action</a1> to position<dest>::action</a2>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/a1",
        "/a2",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "dest",
    ]


def test_action_statements_block_with_mixed_create_and_move_statements(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "        move the particle in position<run> to position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "run",
        "run",
        "done",
    ]


def test_action_statements_block_with_move_particle_mixed_local_and_global(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        move the particle in position<local_src> to position</global_dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "local_src",
    ]
