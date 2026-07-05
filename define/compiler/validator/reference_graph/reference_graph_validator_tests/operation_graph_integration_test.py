import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"

_DESTRUCTORS_NOT_RECORDED = (
    "destructor triggers are not recorded in the operation graph"
)


def test_single_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(item)": [],
    }


def test_two_dependent_operations(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(item)": [],
        "test.move(item, dest)": ["test.create(item)"],
    }


def test_three_operation_chain(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "        destroy the particle in position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(item)": [],
        "test.move(item, dest)": ["test.create(item)"],
        "test.destroy(dest)": ["test.move(item, dest)"],
    }


def test_repeated_operation_on_same_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(item)": [],
        "test.destroy(item)": ["test.create(item)"],
        "test.create(item)#2": ["test.destroy(item)"],
    }


def test_join_operation_waits_on_two_predecessors(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<b>.\n"
                "        destroy the particle in position<b>.\n"
                "        move the particle in position<a> to position<b>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(a)": [],
        "test.create(b)": [],
        "test.destroy(b)": ["test.create(b)"],
        "test.move(a, b)": ["test.create(a)", "test.destroy(b)"],
    }


def test_fan_out_two_operations_depend_on_one(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<a>.\n"
                "        move the particle in position<a> to position<b>.\n"
                "        create a particle in position<a>.\n"
                "        destroy the particle in position<b>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(a)": [],
        "test.move(a, b)": ["test.create(a)"],
        "test.create(a)#2": ["test.move(a, b)"],
        "test.destroy(b)": ["test.move(a, b)"],
    }


def test_occupied_requirement_on_input_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<input>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.destroy(input)": [],
    }


def test_occupied_requirement_on_parent_of_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.destroy(input::/child)": [],
    }


def test_occupied_requirement_on_grandparent_of_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild>.\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>::position</child>::position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.destroy(input::/child::/grandchild)": [],
    }


def test_multiway_join_and_fan_out(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a>.\n"
                "        create a particle in position<box>::position</b>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/a)": ["test.create(box)"],
        "test.create(box::/b)": ["test.create(box)"],
        "test.destroy(box)": [
            "test.create(box::/a)",
            "test.create(box::/b)",
        ],
    }


def test_destroy_reduces_to_the_deepest_touched_descendant(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild>.\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        create a particle in position<box>::position</child>::position</grandchild>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The Child Rule drops a touched descendant that a deeper touched one
    # supersedes: the grandchild reaches the child and the box through its own
    # ancestor chain, so the destroy needs only the grandchild.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.create(box::/child::/grandchild)": ["test.create(box::/child)"],
        "test.destroy(box)": [
            "test.create(box::/child::/grandchild)",
        ],
    }


def test_destroy_reduces_its_own_position_create_edge(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The destroy keeps its own-position edge to create(box) only when no touched
    # child is more recent. Here create(box::/child) is more recent and already
    # reaches create(box), so the destroy drops the edge and waits on the child.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.destroy(box)": [
            "test.create(box::/child)",
        ],
    }


def test_refill_does_not_repeat_the_ancestor_edge(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<parent> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<parent>.\n"
                "        create a particle in position<parent>::position</child>.\n"
                "        destroy the particle in position<parent>::position</child>.\n"
                "        create a particle in position<parent>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The refill needs no fresh ancestor edge to create(parent): the destroy it
    # follows is more recent than create(parent) and already reaches it, so the
    # refill inherits the ordering transitively.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.destroy(parent::/child)": ["test.create(parent::/child)"],
        "test.create(parent::/child)#2": ["test.destroy(parent::/child)"],
    }


def test_empty_after_ancestor_move_refill_waits_on_the_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<source> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>.\n"
                "        create a particle in position<source>.\n"
                "        create a particle in position<source>::position</child>.\n"
                "        move the particle in position<source> to position<box>.\n"
                "        destroy the particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The move refills box::/child without operating on that key directly, so it
    # is the most recent operation on that position's ancestor chain. The
    # second destroy of box::/child waits on the move and cannot run before the
    # particle the move placed there arrives; the stale earlier destroy is not
    # repeated, since the move already reaches it.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.destroy(box::/child)": ["test.create(box::/child)"],
        "test.destroy(box)": ["test.destroy(box::/child)"],
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, box)": [
            "test.destroy(box)",
            "test.create(source::/child)",
        ],
        "test.destroy(box::/child)#2": ["test.move(source, box)"],
        "test.destroy(box)#2": ["test.destroy(box::/child)#2"],
    }


def test_deep_ancestor_move_refill_reduces_the_whole_stale_chain(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
            "mid.dfn": (
                "define the potential position<my.domain.com:my_lib:/mid> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</mid>.\n"
                "        }\n"
                "    }\n"
                "    define the position<source> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</mid>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</mid>.\n"
                "        create a particle in position<box>::position</mid>::position</leaf>.\n"
                "        destroy the particle in position<box>::position</mid>::position</leaf>.\n"
                "        destroy the particle in position<box>::position</mid>.\n"
                "        destroy the particle in position<box>.\n"
                "        create a particle in position<source>.\n"
                "        create a particle in position<source>::position</mid>.\n"
                "        create a particle in position<source>::position</mid>::position</leaf>.\n"
                "        move the particle in position<source> to position<box>.\n"
                "        destroy the particle in position<box>::position</mid>::position</leaf>.\n"
                "        destroy the particle in position<box>::position</mid>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The move refills the whole box::/mid::/leaf chain without operating on those
    # keys directly, leaving stale operations on both box::/mid::/leaf and
    # box::/mid. The second destroy of box::/mid::/leaf takes only the move -- the
    # most recent operation on its chain -- dropping both the stale leaf and the
    # stale intermediate mid, since the move reaches them transitively.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/mid)": ["test.create(box)"],
        "test.create(box::/mid::/leaf)": ["test.create(box::/mid)"],
        "test.destroy(box::/mid::/leaf)": ["test.create(box::/mid::/leaf)"],
        "test.destroy(box::/mid)": ["test.destroy(box::/mid::/leaf)"],
        "test.destroy(box)": ["test.destroy(box::/mid)"],
        "test.create(source)": [],
        "test.create(source::/mid)": ["test.create(source)"],
        "test.create(source::/mid::/leaf)": ["test.create(source::/mid)"],
        "test.move(source, box)": [
            "test.destroy(box)",
            "test.create(source::/mid::/leaf)",
        ],
        "test.destroy(box::/mid::/leaf)#2": ["test.move(source, box)"],
        "test.destroy(box::/mid)#2": ["test.destroy(box::/mid::/leaf)#2"],
        "test.destroy(box)#2": ["test.destroy(box::/mid)#2"],
    }


def test_move_parent_waits_on_touched_descendants(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<src> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<src>.\n"
                "        create a particle in position<src>::position</child>.\n"
                "        move the particle in position<src> to position<dest>.\n"
                "        destroy the particle in position<dest>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(src)": [],
        "test.create(src::/child)": ["test.create(src)"],
        "test.move(src, dest)": ["test.create(src::/child)"],
        "test.destroy(dest::/child)": ["test.move(src, dest)"],
    }


def test_move_into_emptied_target_waits_on_the_target_destroy(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<src> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<dest>.\n"
                "        create a particle in position<dest>::position</child>.\n"
                "        destroy the particle in position<dest>::position</child>.\n"
                "        destroy the particle in position<dest>.\n"
                "        create a particle in position<src>.\n"
                "        create a particle in position<src>::position</child>.\n"
                "        move the particle in position<src> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The move waits on the target's destroy (the most recent operation on the
    # target's ancestor chain), which already waits on the destroy of the
    # target's former child (the Child Rule). So the move is ordered after that
    # child-destroy transitively -- no redundant direct edge to it.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(dest)": [],
        "test.create(dest::/child)": ["test.create(dest)"],
        "test.destroy(dest::/child)": ["test.create(dest::/child)"],
        "test.destroy(dest)": ["test.destroy(dest::/child)"],
        "test.create(src)": [],
        "test.create(src::/child)": ["test.create(src)"],
        "test.move(src, dest)": [
            "test.destroy(dest)",
            "test.create(src::/child)",
        ],
    }


def test_auto_destruction_records_destroy_operations(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<first>.\n"
                "        define the position<second>.\n"
                "        create a particle in position<first>.\n"
                "        create a particle in position<second>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.destroy(second)": ["test.create(second)"],
        "test.destroy(first)": ["test.create(first)"],
    }


def test_trigger_inlines_callee(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output)": ["test.create(gateway::/other::trigger_pos)"],
    }


def test_caller_operation_waits_on_callee_output_not_later_callee_operations(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    define the position<late>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "        create a particle in position<late>.\n"
                "        destroy the particle in position<late>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<output>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output)": ["test.create(gateway::/other::trigger_pos)"],
        "other.create(late)": ["test.create(gateway::/other::trigger_pos)"],
        "other.destroy(late)": ["other.create(late)"],
        "test.destroy(gateway::/other::output)": ["other.create(output)"],
    }


def test_caller_operation_waits_on_callee_move_output(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<trigger_pos> to position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<output>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(trigger_pos, output)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
        "test.destroy(gateway::/other::output)": ["other.move(trigger_pos, output)"],
    }


def test_caller_operation_waits_on_callee_destroy_output(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<output>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<gateway>::action</other>::position<output>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(output)": ["test.create(gateway::/other::trigger_pos)"],
        "test.create(gateway::/other::output)#2": ["other.destroy(output)"],
    }


def test_trigger_inlines_callee_internal_dependencies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<scratch>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<scratch>.\n"
                "        destroy the particle in position<scratch>.\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(scratch)": ["test.create(gateway::/other::trigger_pos)"],
        "other.destroy(scratch)": ["other.create(scratch)"],
        "other.create(output)": ["test.create(gateway::/other::trigger_pos)"],
    }


def test_constructor_trigger_inlines_constructor(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker>.\n"
            ),
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</marker>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "construct.create(/marker)": ["test.create(box)"],
    }


def test_multi_level_constructor_chain(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
            "construct_c.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_c> {\n"
                "    it also assigns the position</leaf>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential position<my.domain.com:my_lib:/inner> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</construct_c>.\n"
                "    }\n"
                "}\n"
            ),
            "construct_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_b> {\n"
                "    it also assigns the position</inner>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</inner>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "construct_b.create(/inner)": ["test.create(box)"],
        "construct_c.create(/leaf)": ["construct_b.create(/inner)"],
    }


def test_multiple_constructors_all_fire_on_one_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker_a.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker_a>.\n"
            ),
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</marker_a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</marker_a>.\n"
                "    }\n"
                "}\n"
            ),
            "marker_b.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker_b>.\n"
            ),
            "construct_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_b> {\n"
                "    it also assigns the position</marker_b>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</marker_b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct_a>.\n"
                "            it has the action</construct_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "construct_a.create(/marker_a)": ["test.create(box)"],
        "construct_b.create(/marker_b)": ["test.create(box)"],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
def test_multiple_destructors_all_fire_on_destroy(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destruct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/destruct_a> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "        destroy the particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "destruct_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/destruct_b> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "        destroy the particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destruct_a>.\n"
                "                it has the action</destruct_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.destroy(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.destroy(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
def test_caller_added_destructor_fires_in_callee(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "        destroy the particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "callee.dfn": (
                "define the potential action<my.domain.com:my_lib:/callee> {\n"
                "    define the position<target>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</callee>.\n"
                "            }\n"
                "        }\n"
                "        define the position<carrier> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<carrier>.\n"
                "        move the particle in position<carrier> to position<box>::action</callee>::position<target>.\n"
                "        create a particle in position<box>::action</callee>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # Aspirational: when destructor triggers are recorded, callee.destroy(target)
    # fires the caller-added destructor on the particle it destroys, inlining the
    # destructor's operations.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.create(box::/callee::run)"],
        "destructor.create(_noop)": ["callee.destroy(target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box)": [
            "test.create(box)",
            "test.create(box::/callee::run)",
        ],
    }
