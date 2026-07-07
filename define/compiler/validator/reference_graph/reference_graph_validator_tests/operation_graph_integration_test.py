# TODO: Split this file in two, moving the caller-requirement tests (the
# RequirementNode resolution cases) into their own file and leaving the plain
# operation-graph / guarantee cases here.

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

_MULTI_LEVEL_REQUIREMENTS_NOT_PROPAGATED = (
    "a caller requirement is resolved only against the immediate caller, so a"
    " requirement that propagates up several call levels resolves to the trigger"
    " instead of the op further up the stack that satisfies it; the callee's"
    " RequirementNodes need re-propagating into each caller"
)

_MOVE_CARRIED_CHILD_DOES_NOT_SATISFY_REQUIREMENT = (
    "a move that carries a child into a callee's interface position does not yet"
    " satisfy the callee's propagated occupied requirement on that child, so a"
    " spurious requirement violation is reported; this is a requirement-checking"
    " limitation, not an operation-graph one -- the graph already resolves the"
    " callee's operations to the carrying move"
)

_TRIGGER_POSITION_READ_LOSES_ITS_TRIGGER_EDGE = (
    "an operation that reads the trigger position falls back to the trigger edge"
    " only when all of its requirement seams are unresolved; once another seam"
    " resolves to a real caller operation, the trigger-position read keeps no"
    " edge to the trigger fill and can run while the trigger position is still"
    " empty"
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


def test_second_move_of_a_carried_child_waits_on_the_first_move(
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
                "    define the position<basket>.\n"
                "    define the position<crate>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        move the particle in position<box> to position<basket>.\n"
                "        move the particle in position<basket> to position<crate>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The first move carries the child to basket::/child without operating on
    # that key directly, so the second move empties basket without finding a
    # direct operation on the carried child. It waits on the first move, the
    # most recent operation on basket's ancestor chain.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.move(box, basket)": ["test.create(box::/child)"],
        "test.move(basket, crate)": ["test.move(box, basket)"],
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
    # <output> is both a requirement (the callee destroys it) and a guarantee (the
    # callee leaves it empty), so the trigger's guarantee overwrites its last
    # operation in the caller graph. other.destroy(output) still resolves to the
    # caller fill that satisfies the requirement, not to the guarantee node or the
    # trigger. The caller's refill then waits on the callee destroy's split point.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(output)": ["test.create(gateway::/other::output)"],
        "test.create(gateway::/other::output)#2": ["other.destroy(output)"],
    }


def test_empty_requirement_waits_on_the_caller_destroy_that_clears_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<slot>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<slot>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<slot>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # other.create(slot) needs <slot> empty, so it should wait on test.destroy(slot),
    # which clears the position, and on nothing else. It needs no edge to the
    # trigger: we know the action triggers, and the create's only precondition is that
    # <slot> is empty. (The destroy transitively orders it after the callee's parent
    # particle was created, since the destroy depends on it.)
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::slot)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::slot)": ["test.create(gateway::/other::slot)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.destroy(gateway::/other::slot)"],
    }


def test_occupied_requirement_waits_on_the_caller_create_that_fills_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<input>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<input>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # other.destroy(input) needs only <input> occupied, so it should wait _only_
    # test.create(input), which fills it -- and on nothing else.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::input)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(input)": ["test.create(gateway::/other::input)"],
    }


def test_empty_requirement_waits_on_the_caller_move_that_clears_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::action</other>::position<slot>.\n"
                "        move the particle in position<gateway>::action</other>::position<slot> to position<sink>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # A move-out clears the requirement just as a destroy does, so other.create(slot)
    # should wait on the move that empties <slot>, and on nothing else.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::slot)": ["test.create(gateway)"],
        "test.move(gateway::/other::slot, sink)": [
            "test.create(gateway::/other::slot)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.move(gateway::/other::slot, sink)"],
    }


def test_move_joins_an_in_body_source_and_a_requirement_target(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src>.\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<dest>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<dest>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<dest>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # A move has both a fill and an empty side, so it joins two kinds of
    # predecessor at once: it empties the in-body-created <src> (an ordinary
    # operation) and fills the caller-controlled empty-requirement <dest> (a
    # requirement the caller satisfies by emptying it before the trigger).
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::dest)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::dest)": ["test.create(gateway::/other::dest)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(src)": ["test.create(gateway::/other::trigger_pos)"],
        "other.move(src, dest)": [
            "other.create(src)",
            "test.destroy(gateway::/other::dest)",
        ],
    }


def test_child_empty_requirement_waits_on_the_caller_empty_of_the_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::position</child>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<box>.\n"
                "        create a particle in position<gateway>::action</other>::position<box>::position</child>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<box>::position</child>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The callee fills the child box::/child, whose EMPTY requirement the caller
    # satisfies by emptying that same child. other.create(box::/child) waits on
    # the caller destroy of the child, not on the trigger.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.destroy(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child)": ["test.destroy(gateway::/other::box::/child)"],
    }


def test_empty_by_default_child_requirements_branch_from_the_caller_parent_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "            it has the position</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::position</a>.\n"
                "        create a particle in position<box>::position</b>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<box>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # box::/a and box::/b are empty by default, so the caller never touches them.
    # The callee's fills only need box present, so they branch straight from the
    # caller's fill of box rather than waiting on a caller empty or the trigger.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/a)": ["test.create(gateway::/other::box)"],
        "other.create(box::/b)": ["test.create(gateway::/other::box)"],
    }


def test_occupied_grandchild_requirement_waits_on_the_caller_fill(
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
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<box>::position</child>::position</grandchild>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<box>.\n"
                "        create a particle in position<gateway>::action</other>::position<box>::position</child>.\n"
                "        create a particle in position<gateway>::action</other>::position<box>::position</child>::position</grandchild>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The callee reads a grandchild-depth contracted position, so its OCCUPIED
    # requirement resolves to the caller fill of that grandchild.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child::/grandchild)"
        ],
    }


def test_empty_grandchild_requirement_waits_on_the_caller_empty(
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
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::position</child>::position</grandchild>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<box>.\n"
                "        create a particle in position<gateway>::action</other>::position<box>::position</child>.\n"
                "        create a particle in position<gateway>::action</other>::position<box>::position</child>::position</grandchild>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<box>::position</child>::position</grandchild>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The callee fills a grandchild-depth contracted position, so its EMPTY
    # requirement resolves to the caller empty of that same grandchild.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.destroy(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child::/grandchild)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child::/grandchild)": [
            "test.destroy(gateway::/other::box::/child::/grandchild)"
        ],
    }


def test_implied_position_grandchildren_wait_on_the_direct_caller_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild1.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild1>.\n"
            ),
            "grandchild2.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild2>.\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild1>.\n"
                "        it has the position</grandchild2>.\n"
                "    }\n"
                "}\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>::position</child>::position</grandchild1>.\n"
                "        create a particle in position</parent>::position</child>::position</grandchild2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</parent>.\n"
                "    it also assigns the action</inner>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>.\n"
                "        create a particle in position</parent>::position</child>.\n"
                "        create a particle in action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /test fills the shared global /parent and /parent::/child, then triggers the
    # implied /inner directly. /inner's grandchild fills need /parent::/child
    # present, so they resolve to /test's fill of it -- the implied position hangs
    # off the callee's parent particle, not under its action chain.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }


@pytest.mark.xfail(strict=True, reason=_MULTI_LEVEL_REQUIREMENTS_NOT_PROPAGATED)
def test_occupied_requirement_two_levels_up_waits_on_the_caller_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</middle>::position<gw>.\n"
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<slot>.\n"
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # inner.destroy(slot) reads a position whose requirement propagates up through
    # /middle (which never touches it) to /test. It must wait on the /test fill
    # that satisfies it, not on /middle's trigger of /inner. It resolves to the
    # trigger today because a RequirementNode is matched only against the
    # immediate caller.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::slot)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/middle::trigger_pos)"
        ],
        "inner.destroy(slot)": ["test.create(box::/middle::gw::/inner::slot)"],
    }


@pytest.mark.xfail(strict=True, reason=_MULTI_LEVEL_REQUIREMENTS_NOT_PROPAGATED)
def test_occupied_requirement_two_levels_up_waits_on_the_caller_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<source>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</middle>::position<gw>.\n"
                "        move the particle in position<source> to position<box>::action</middle>::position<gw>::action</inner>::position<slot>.\n"
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # A move that lands the particle two call levels up satisfies the propagated
    # requirement, so inner.destroy(slot) must wait on that move rather than on
    # /middle's trigger of /inner.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(source)": [],
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.move(source, box::/middle::gw::/inner::slot)": [
            "test.create(source)",
            "test.create(box::/middle::gw)",
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/middle::trigger_pos)"
        ],
        "inner.destroy(slot)": ["test.move(source, box::/middle::gw::/inner::slot)"],
    }


@pytest.mark.xfail(strict=True, reason=_MULTI_LEVEL_REQUIREMENTS_NOT_PROPAGATED)
def test_implied_position_children_wait_on_the_two_levels_up_caller_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child1.dfn": "define the potential position<my.domain.com:my_lib:/child1>.\n",
            "child2.dfn": "define the potential position<my.domain.com:my_lib:/child2>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child1>.\n"
                "        it has the position</child2>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>::position</child1>.\n"
                "        create a particle in position</parent>::position</child2>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</inner>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</parent>.\n"
                "    it also assigns the action</middle>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>.\n"
                "        create a particle in action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /parent is a shared global implied position: /test fills it, then triggers
    # /middle, which triggers /inner, which fills its children. Each child fill
    # needs only /parent present, so it should wait on /test's fill of /parent --
    # two call levels up -- not on /middle's trigger of /inner.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(/parent)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": ["test.create(/middle::trigger_pos)"],
        "inner.create(/parent::/child1)": ["test.create(/parent)"],
        "inner.create(/parent::/child2)": ["test.create(/parent)"],
    }


@pytest.mark.xfail(strict=True, reason=_MULTI_LEVEL_REQUIREMENTS_NOT_PROPAGATED)
def test_implied_position_grandchildren_wait_on_the_two_levels_up_caller_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild1.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild1>.\n"
            ),
            "grandchild2.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild2>.\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild1>.\n"
                "        it has the position</grandchild2>.\n"
                "    }\n"
                "}\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>::position</child>::position</grandchild1>.\n"
                "        create a particle in position</parent>::position</child>::position</grandchild2>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</inner>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</parent>.\n"
                "    it also assigns the action</middle>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>.\n"
                "        create a particle in position</parent>::position</child>.\n"
                "        create a particle in action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /test fills /parent and /parent::/child; /inner (two levels down) fills the
    # grandchildren. Each grandchild fill needs /parent::/child present, so it
    # should wait on /test's fill of /parent::/child, not on /middle's trigger.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": ["test.create(/middle::trigger_pos)"],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }


@pytest.mark.xfail(strict=True, reason=_MOVE_CARRIED_CHILD_DOES_NOT_SATISFY_REQUIREMENT)
def test_moved_in_parent_children_branch_from_the_carrying_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</a>.\n"
                "        it has the position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::position</parent>::position</a>.\n"
                "        create a particle in position<input>::position</parent>::position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<gw> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<gw>.\n"
                "        move the particle in position<iface> to position<gw>::action</inner>::position<input>.\n"
                "        create a particle in position<gw>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mw>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>.\n"
                "        create a particle in position<mw>::action</middle>::position<iface>::position</parent>.\n"
                "        create a particle in position<mw>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # middle moves iface (carrying its </parent> child) into inner::input. inner
    # then fills the empty-by-default grandchildren parent::/a and parent::/b;
    # each branches from the move that placed the parent, since the move's target
    # (gw::/inner::input) is the nearest ancestor the caller touched.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(mw)": [],
        "test.create(mw::/middle::iface)": ["test.create(mw)"],
        "test.create(mw::/middle::iface::/parent)": ["test.create(mw::/middle::iface)"],
        "test.create(mw::/middle::run)": ["test.create(mw)"],
        "middle.create(gw)": ["test.create(mw::/middle::run)"],
        "middle.move(iface, gw::/inner::input)": [
            "middle.create(gw)",
            "test.create(mw::/middle::iface)",
        ],
        "middle.create(gw::/inner::run)": ["middle.create(gw)"],
        "inner.create(input::/parent::/a)": ["middle.move(iface, gw::/inner::input)"],
        "inner.create(input::/parent::/b)": ["middle.move(iface, gw::/inner::input)"],
        "middle.destroy(gw)": [
            "middle.move(iface, gw::/inner::input)",
            "middle.create(gw::/inner::run)",
        ],
    }


def test_occupied_requirement_resolves_to_the_most_recent_fill_before_the_trigger(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
            "helper.dfn": (
                "define the potential action<my.domain.com:my_lib:/helper> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<slot> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source>.\n"
                "    define the position<temp>.\n"
                "    define the position<gw_a> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</worker>.\n"
                "        }\n"
                "    }\n"
                "    define the position<gw_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</helper>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<source>.\n"
                "        create a particle in position<gw_a>.\n"
                "        create a particle in position<gw_b>.\n"
                "        move the particle in position<source> to position<gw_a>::action</worker>::position<slot>.\n"
                "        move the particle in position<gw_a>::action</worker>::position<slot> to position<temp>.\n"
                "        move the particle in position<temp> to position<gw_b>::action</helper>::position<slot>.\n"
                "        create a particle in position<gw_b>::action</helper>::position<trigger_pos>.\n"
                "        move the particle in position<gw_b>::action</helper>::position<out> to position<gw_a>::action</worker>::position<slot>.\n"
                "        create a particle in position<gw_a>::action</worker>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The widget is moved into worker::slot, back out, through helper, then into
    # worker::slot a second time before worker triggers. worker.destroy(slot) must
    # resolve its requirement to that second fill -- the most recent caller op that
    # leaves slot occupied before the trigger -- not the stale first fill; binding
    # to the first fill would race the move that empties slot again. Likewise
    # helper.move(slot, out) waits on the caller fill of helper::slot, not the
    # helper trigger.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(source)": [],
        "test.create(gw_a)": [],
        "test.create(gw_b)": [],
        "test.move(source, gw_a::/worker::slot)": [
            "test.create(source)",
            "test.create(gw_a)",
        ],
        "test.move(gw_a::/worker::slot, temp)": [
            "test.move(source, gw_a::/worker::slot)"
        ],
        "test.move(temp, gw_b::/helper::slot)": [
            "test.create(gw_b)",
            "test.move(gw_a::/worker::slot, temp)",
        ],
        "test.create(gw_b::/helper::trigger_pos)": ["test.create(gw_b)"],
        "helper.move(slot, out)": ["test.move(temp, gw_b::/helper::slot)"],
        "test.move(gw_b::/helper::out, gw_a::/worker::slot)": [
            "test.move(gw_a::/worker::slot, temp)",
            "helper.move(slot, out)",
        ],
        "test.create(gw_a::/worker::trigger_pos)": ["test.create(gw_a)"],
        "worker.destroy(slot)": ["test.move(gw_b::/helper::out, gw_a::/worker::slot)"],
    }


def test_empty_requirement_resolves_to_the_most_recent_empty_before_the_trigger(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</filler>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</filler>::position<slot>.\n"
                "        destroy the particle in position<gw>::action</filler>::position<slot>.\n"
                "        create a particle in position<gw>::action</filler>::position<slot>.\n"
                "        destroy the particle in position<gw>::action</filler>::position<slot>.\n"
                "        create a particle in position<gw>::action</filler>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # slot is filled and emptied twice before filler triggers. filler.create(slot)
    # needs slot empty, so it must resolve to the second (most recent) destroy
    # before the trigger, not the first -- picking the first would leave it racing
    # the refill.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/filler::slot)": ["test.create(gw)"],
        "test.destroy(gw::/filler::slot)": ["test.create(gw::/filler::slot)"],
        "test.create(gw::/filler::slot)#2": ["test.destroy(gw::/filler::slot)"],
        "test.destroy(gw::/filler::slot)#2": ["test.create(gw::/filler::slot)#2"],
        "test.create(gw::/filler::trigger_pos)": ["test.create(gw)"],
        "filler.create(slot)": ["test.destroy(gw::/filler::slot)#2"],
    }


def test_occupied_requirement_resolves_to_the_constraint_satisfying_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "move.dfn": (
                "define the potential action<my.domain.com:my_lib:/move> {\n"
                "    define the position<run>.\n"
                "    define the position<input>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<input> to position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box1> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box2>.\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<action_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</move>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<action_holder>.\n"
                "        create a particle in position<box1>.\n"
                "        create a particle in position<box2>.\n"
                "        move the particle in position<box2> to position<action_holder>::action</move>::position<input>.\n"
                "        move the particle in position<action_holder>::action</move>::position<input> to position<box2>.\n"
                "        move the particle in position<box1> to position<action_holder>::action</move>::position<input>.\n"
                "        create a particle in position<action_holder>::action</move>::position<run>.\n"
                "        move the particle in position<action_holder>::action</move>::position<output> to position<dest>.\n"
                "        create a particle in position<dest>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # move::input is filled from box2, emptied back to box2, then filled from box1
    # before move triggers. move.move(input, output) must resolve its requirement to
    # the box1 fill -- the most recent fill before the trigger -- not the box2 fill.
    # The constraint makes this a safety issue, not just ordering: only box1's
    # particle has position</a>, and the move feeds dest, which requires it. Binding
    # to the box2 fill would let the move run with box2's particle and carry it into
    # dest, violating the constraint.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(action_holder)": [],
        "test.create(box1)": [],
        "test.create(box2)": [],
        "test.move(box2, action_holder::/move::input)": [
            "test.create(action_holder)",
            "test.create(box2)",
        ],
        "test.move(action_holder::/move::input, box2)": [
            "test.move(box2, action_holder::/move::input)"
        ],
        "test.move(box1, action_holder::/move::input)": [
            "test.create(box1)",
            "test.move(action_holder::/move::input, box2)",
        ],
        "test.create(action_holder::/move::run)": ["test.create(action_holder)"],
        "move.move(input, output)": ["test.move(box1, action_holder::/move::input)"],
        "test.move(action_holder::/move::output, dest)": ["move.move(input, output)"],
        "test.create(dest::/a)": ["test.move(action_holder::/move::output, dest)"],
    }


def test_retriggered_action_resolves_requirements_within_each_invocation(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "maker.dfn": (
                "define the potential action<my.domain.com:my_lib:/maker> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<first_result>.\n"
                "    define the position<second_result>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</maker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "        move the particle in position<gw>::action</maker>::position<out> to position<first_result>.\n"
                "        destroy the particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "        create a particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "        move the particle in position<gw>::action</maker>::position<out> to position<second_result>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # maker is triggered twice: its trigger position is filled, emptied, and
    # refilled, so both invocations are inlined. Each invocation's EMPTY
    # requirement on <out> resolves within its own window, bounded by its own
    # trigger: invocation 1's create(out) falls back to its trigger fill (the
    # caller never touched <out> before it), while invocation 2's create(out)#2
    # waits on the caller's drain of invocation 1's output -- the most recent op
    # on <out> before the second trigger -- and not on the stale first window or
    # on its own trigger. Without that edge, invocation 2 could race the drain
    # and put two particles in <out>.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/maker::trigger_pos)": ["test.create(gw)"],
        "maker.create(out)": ["test.create(gw::/maker::trigger_pos)"],
        "test.move(gw::/maker::out, first_result)": ["maker.create(out)"],
        "test.destroy(gw::/maker::trigger_pos)": [
            "test.create(gw::/maker::trigger_pos)"
        ],
        "test.create(gw::/maker::trigger_pos)#2": [
            "test.destroy(gw::/maker::trigger_pos)"
        ],
        "maker.create(out)#2": ["test.move(gw::/maker::out, first_result)"],
        "test.move(gw::/maker::out, second_result)": ["maker.create(out)#2"],
    }


def test_operation_reading_the_trigger_position_depends_on_the_trigger_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "consumer.dfn": (
                "define the potential action<my.domain.com:my_lib:/consumer> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</consumer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</consumer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # An operation that reads the trigger position genuinely depends on the caller
    # op that fills it -- this trigger edge is a real data dependency.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/consumer::trigger_pos)": ["test.create(gw)"],
        "consumer.destroy(trigger_pos)": ["test.create(gw::/consumer::trigger_pos)"],
    }


@pytest.mark.xfail(strict=True, reason=_TRIGGER_POSITION_READ_LOSES_ITS_TRIGGER_EDGE)
def test_trigger_position_read_keeps_the_trigger_edge_when_a_requirement_resolves(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<in>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<in> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</worker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</worker>::position<out>.\n"
                "        destroy the particle in position<gw>::action</worker>::position<out>.\n"
                "        create a particle in position<gw>::action</worker>::position<in>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The move reads <in>, the trigger position, so it needs the trigger fill as
    # a real data dependency -- just as in the trigger-read test above. But its
    # EMPTY requirement on <out> resolves to the caller's destroy, and that
    # resolved edge must not displace the trigger edge: with only the destroy
    # edge, the move could run at destroy-time, while <in> is still empty.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::out)": ["test.create(gw)"],
        "test.destroy(gw::/worker::out)": ["test.create(gw::/worker::out)"],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        "worker.move(in, out)": [
            "test.destroy(gw::/worker::out)",
            "test.create(gw::/worker::in)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_TRIGGER_POSITION_READ_LOSES_ITS_TRIGGER_EDGE)
def test_trigger_position_read_keeps_the_trigger_edge_when_an_occupied_requirement_resolves(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<in>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<in> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in> to position<box>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</worker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</worker>::position<box>.\n"
                "        create a particle in position<gw>::action</worker>::position<in>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The OCCUPIED counterpart of the test above: the move reads <in>, the
    # trigger position, while its fill target needs <box> occupied -- a
    # requirement that resolves (through the untouched <box>::</y> child seam's
    # parent) to the caller's fill of <box>. That resolved edge must not
    # displace the trigger edge: with only the <box> edge, the move could run
    # as soon as <box> is filled, while <in> is still empty.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::box)": ["test.create(gw)"],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        "worker.move(in, box::/y)": [
            "test.create(gw::/worker::box)",
            "test.create(gw::/worker::in)",
        ],
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
