from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors


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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
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
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.destroy(second)": ["test.create(second)"],
        "test.destroy(first)": ["test.create(first)"],
    }


def test_destroy_of_the_trigger_particle(
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
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The destroy waits on the caller operation that filled the trigger position,
    # which is not an operation of this action.
    assert operation_dependencies(result.operation_graphs) == {
        "test.destroy(run)": [],
    }


def test_move_of_the_trigger_particle(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<run> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.move(run, dest)": [],
    }


def test_operation_on_a_child_of_the_trigger_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.destroy(run::/child)": [],
    }


def test_destroy_of_the_trigger_position_waits_on_its_child_destroy(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>::position</child>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.destroy(run::/child)": [],
        "test.destroy(run)": ["test.destroy(run::/child)"],
    }


def test_create_and_destroy_of_an_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/implied)": [],
        "test.destroy(/implied)": ["test.create(/implied)"],
    }


def test_operations_on_a_child_of_an_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        create a particle in position</implied>::position</child>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/implied)": [],
        "test.create(/implied::/child)": ["test.create(/implied)"],
        "test.destroy(/implied)": ["test.create(/implied::/child)"],
    }


def test_occupied_requirement_on_an_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.destroy(/implied)": [],
    }


def test_move_from_an_interface_position_to_an_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    define the position<source>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<source>.\n"
                "        move the particle in position<source> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.move(source, /implied)": ["test.create(source)"],
    }


def test_move_from_an_implied_position_to_an_interface_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.move(/implied, dest)": [],
    }


def test_move_of_an_implied_position_carries_its_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied> to position<dest>.\n"
                "        destroy the particle in position<dest>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The move carries the child to dest::/child without operating on that key
    # directly, so the destroy waits on the move.
    assert operation_dependencies(result.operation_graphs) == {
        "test.move(/implied, dest)": [],
        "test.destroy(dest::/child)": ["test.move(/implied, dest)"],
    }


def test_auto_destruction_leaves_the_implied_position_alone(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The implied position belongs to the particle the action is assigned to, not
    # to the action's body, so the block end destroys only position<local>.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(local)": [],
        "test.create(/implied)": [],
        "test.destroy(local)": ["test.create(local)"],
    }


def test_move_of_the_trigger_particle_into_a_local_position(
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
                "        define the position<local>.\n"
                "        move the particle in position<run> to position<local>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The trigger particle ends the block in a position the block defined, so the
    # block end destroys it.
    assert operation_dependencies(result.operation_graphs) == {
        "test.move(run, local)": [],
        "test.destroy(local)": ["test.move(run, local)"],
    }


def test_move_of_the_trigger_particle_into_an_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<run> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.move(run, /implied)": [],
    }
