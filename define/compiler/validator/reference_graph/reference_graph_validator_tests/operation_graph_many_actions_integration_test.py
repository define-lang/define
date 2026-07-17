import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS = (
    "the operation graph does not preserve the Empty Rule across action triggerings"
)


def test_actions_with_identically_named_child_actions_have_distinct_instances(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<scratch>.\n"
                "        create a particle in position<scratch>.\n"
                "    }\n"
                "}\n"
            ),
            "first.dfn": (
                "define the potential action<my.domain.com:my_lib:/first> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "second.dfn": (
                "define the potential action<my.domain.com:my_lib:/second> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</first>.\n"
                "    it also assigns the action</second>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</first>::position<trigger_pos>.\n"
                "        create a particle in action</second>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/first::trigger_pos)": [],
        "test.create(/second::trigger_pos)": [],
        "first.create(box)": [],
        "first.create(box::/inner::trigger_pos)": ["first.create(box)"],
        "first.destroy(box)": ["first.create(box::/inner::trigger_pos)"],
        "second.create(box)": [],
        "second.create(box::/inner::trigger_pos)": ["second.create(box)"],
        "second.destroy(box)": ["second.create(box::/inner::trigger_pos)"],
        "first:inner.create(scratch)": ["first.create(box)"],
        "first:inner.destroy(scratch)": ["first:inner.create(scratch)"],
        "second:inner.create(scratch)": ["second.create(box)"],
        "second:inner.destroy(scratch)": ["second:inner.create(scratch)"],
    }


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
    # /middle (which never touches it) to /test, so it waits on the /test fill that
    # satisfies it -- reached through the RequirementNode /middle materializes for
    # the propagated requirement.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::slot)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.destroy(slot)": ["test.create(box::/middle::gw::/inner::slot)"],
    }


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
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.move(source, box::/middle::gw::/inner::slot)": [
            "test.create(source)",
            "test.create(box::/middle::gw)",
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.destroy(slot)": ["test.move(source, box::/middle::gw::/inner::slot)"],
    }


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_that_clears_it(
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
                "        create a particle in position<slot>.\n"
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
                "        destroy the particle in position<gw>::action</inner>::position<slot>.\n"
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
    # /test fills the slot two levels down, /middle destroys it on the way down,
    # and /inner needs it empty. The intermediate destroy is the most recent
    # operation on the position before the trigger, so inner.create(slot) waits on
    # that destroy, not on the /test fill it superseded.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::slot)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.destroy(gw::/inner::slot)": [
            "test.create(box::/middle::gw::/inner::slot)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(slot)": ["middle.destroy(gw::/inner::slot)"],
    }


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_interface_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<holder>::position</a>.\n"
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
                "        destroy the particle in position<gw>::action</inner>::position<holder>::position</a>.\n"
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
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<holder>.\n"
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<holder>::position</a>.\n"
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The emptied position is a child of /inner's interface position <holder>, not
    # an interface position itself. /test fills holder and the child, /middle
    # destroys the child on the way down, and /inner needs it empty, so
    # inner.create(holder::/a) waits on that destroy rather than on the /test fill
    # it superseded.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::holder)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/middle::gw::/inner::holder)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.destroy(gw::/inner::holder::/a)": [
            "test.create(box::/middle::gw::/inner::holder::/a)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(holder::/a)": ["middle.destroy(gw::/inner::holder::/a)"],
    }


def test_empty_by_default_interface_child_waits_on_the_two_levels_up_caller_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<holder>::position</a>.\n"
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
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<holder>.\n"
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # Nobody empties holder::/a: it is empty by default in the particle /test
    # created in <holder>. /middle never touches it either, so /inner's fill of it
    # waits on the /test create that made its parent, two levels up.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::holder)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(holder::/a)": ["test.create(box::/middle::gw::/inner::holder)"],
    }


def test_empty_requirement_waits_on_a_destroy_by_a_caller_that_does_not_trigger_it(
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
                "        create a particle in position<slot>.\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<mw>::action</middle>::position<gw>::action</inner>::position<slot>.\n"
                "        create a particle in position<mw>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>::action</middle>::position<gw>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>::action</middle>::position<gw>::action</inner>::position<slot>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /outer empties the slot, but /middle is what triggers /inner, and /middle
    # never touches the slot. /inner's empty requirement propagates through
    # /middle to /outer, so inner.create(slot) waits on the destroy performed by a
    # caller that is not the one that triggered it.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::mw)": ["test.create(box)"],
        "test.create(box::/outer::mw::/middle::gw)": ["test.create(box::/outer::mw)"],
        "test.create(box::/outer::mw::/middle::gw::/inner::slot)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.destroy(mw::/middle::gw::/inner::slot)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::slot)"
        ],
        "outer.create(mw::/middle::trigger_pos)": ["test.create(box::/outer::mw)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "inner.create(slot)": ["outer.destroy(mw::/middle::gw::/inner::slot)"],
    }


def test_empty_requirement_waits_on_an_interface_child_destroy_by_a_caller_that_does_not_trigger_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<holder>::position</a>.\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<mw>::action</middle>::position<gw>::action</inner>::position<holder>::position</a>.\n"
                "        create a particle in position<mw>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>::action</middle>::position<gw>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>::action</middle>::position<gw>::action</inner>::position<holder>.\n"
                "        create a particle in position<box>::action</outer>::position<mw>::action</middle>::position<gw>::action</inner>::position<holder>::position</a>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The same four-level shape, with the emptied position a child of /inner's
    # interface position <holder> rather than an interface position itself.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::mw)": ["test.create(box)"],
        "test.create(box::/outer::mw::/middle::gw)": ["test.create(box::/outer::mw)"],
        "test.create(box::/outer::mw::/middle::gw::/inner::holder)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "test.create(box::/outer::mw::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::holder)"
        ],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.destroy(mw::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::holder::/a)"
        ],
        "outer.create(mw::/middle::trigger_pos)": ["test.create(box::/outer::mw)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "inner.create(holder::/a)": [
            "outer.destroy(mw::/middle::gw::/inner::holder::/a)"
        ],
    }


@pytest.mark.xfail(strict=True, reason=_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS)
def test_move_excludes_parent_dependency_when_source_dependency_is_a_guarantee(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destination.dfn": "define the potential position<my.domain.com:my_lib:/destination>.\n",
            "producer.dfn": (
                "define the potential action<my.domain.com:my_lib:/producer> {\n"
                "    define the position<input>.\n"
                "    define the position<result>.\n"
                "    it happens when {\n"
                "        the position<input> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<input> to position<result>.\n"
                "    }\n"
                "}\n"
            ),
            "box.dfn": (
                "define the potential position<my.domain.com:my_lib:/box> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</producer>.\n"
                "        it has the position</destination>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</box>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</box>.\n"
                "        create a particle in position</box>::action</producer>::position<input>.\n"
                "        move the particle in position</box>::action</producer>::position<result> to position</box>::position</destination>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/box)": [],
        "test.create(/box::/producer::input)": ["test.create(/box)"],
        "producer.move(input, result)": ["test.create(/box::/producer::input)"],
        "test.move(/box::/producer::result, /box::/destination)": [
            "producer.move(input, result)"
        ],
    }


def test_callee_operation_without_position_dependencies_waits_on_action_parent(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<result>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<result>.\n"
                "    }\n"
                "}\n"
            ),
            "box.dfn": (
                "define the potential position<my.domain.com:my_lib:/box> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</worker>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</box>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</box>.\n"
                "        create a particle in position</box>::action</worker>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/box)": [],
        "test.create(/box::/worker::trigger_pos)": ["test.create(/box)"],
        "worker.create(result)": ["test.create(/box)"],
    }


@pytest.mark.xfail(strict=True, reason=_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS)
def test_destroy_excludes_callee_operations_superseded_on_child_positions(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<input>.\n"
                "    define the position<result>.\n"
                "    it happens when {\n"
                "        the position<input> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<input> to position<result>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</worker>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</worker>::position<input>.\n"
                "        destroy the particle in position<box>::action</worker>::position<result>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/worker::input)": ["test.create(box)"],
        "worker.move(input, result)": ["test.create(box::/worker::input)"],
        "test.destroy(box::/worker::result)": ["worker.move(input, result)"],
        "test.destroy(box)": ["test.destroy(box::/worker::result)"],
    }


@pytest.mark.xfail(strict=True, reason=_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS)
def test_espresso_operation_graph(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grind.dfn": (
                "define the potential action<my.domain.com:my_lib:/grind> {\n"
                "    define the position<beans>.\n"
                "    define the position<grounds>.\n"
                "    it happens when {\n"
                "        the position<beans> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<beans> to position<grounds>.\n"
                "    }\n"
                "}\n"
            ),
            "heat.dfn": (
                "define the potential action<my.domain.com:my_lib:/heat> {\n"
                "    define the position<cold_water>.\n"
                "    define the position<hot_water>.\n"
                "    it happens when {\n"
                "        the position<cold_water> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<cold_water> to position<hot_water>.\n"
                "    }\n"
                "}\n"
            ),
            "brew.dfn": (
                "define the potential action<my.domain.com:my_lib:/brew> {\n"
                "    define the position<grounds>.\n"
                "    define the position<water>.\n"
                "    define the position<cup>.\n"
                "    define the position<spent_puck>.\n"
                "    it happens when {\n"
                "        the position<water> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<cup>.\n"
                "        destroy the particle in position<water>.\n"
                "        move the particle in position<grounds> to position<spent_puck>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<station> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</grind>.\n"
                "                it has the action</heat>.\n"
                "                it has the action</brew>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<station>.\n"
                "        create a particle in position<station>::action</grind>::position<beans>.\n"
                "        create a particle in position<station>::action</heat>::position<cold_water>.\n"
                "        move the particle in position<station>::action</grind>::position<grounds> to position<station>::action</brew>::position<grounds>.\n"
                "        move the particle in position<station>::action</heat>::position<hot_water> to position<station>::action</brew>::position<water>.\n"
                "        destroy the particle in position<station>::action</brew>::position<cup>.\n"
                "        destroy the particle in position<station>::action</brew>::position<spent_puck>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(station)": [],
        "test.create(station::/grind::beans)": ["test.create(station)"],
        "test.create(station::/heat::cold_water)": ["test.create(station)"],
        "grind.move(beans, grounds)": ["test.create(station::/grind::beans)"],
        "heat.move(cold_water, hot_water)": ["test.create(station::/heat::cold_water)"],
        "test.move(station::/grind::grounds, station::/brew::grounds)": [
            "grind.move(beans, grounds)"
        ],
        "test.move(station::/heat::hot_water, station::/brew::water)": [
            "heat.move(cold_water, hot_water)"
        ],
        "brew.create(cup)": ["test.create(station)"],
        "brew.destroy(water)": [
            "test.move(station::/heat::hot_water, station::/brew::water)"
        ],
        "brew.move(grounds, spent_puck)": [
            "test.move(station::/grind::grounds, station::/brew::grounds)"
        ],
        "test.destroy(station::/brew::cup)": ["brew.create(cup)"],
        "test.destroy(station::/brew::spent_puck)": ["brew.move(grounds, spent_puck)"],
        "test.destroy(station)": [
            "brew.destroy(water)",
            "test.destroy(station::/brew::cup)",
            "test.destroy(station::/brew::spent_puck)",
        ],
    }


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
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child1)": ["test.create(/parent)"],
        "inner.create(/parent::/child2)": ["test.create(/parent)"],
    }


def test_implied_action_inherits_the_current_actions_parent_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<scratch>.\n"
                "        create a particle in position<scratch>.\n"
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
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</middle>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<local> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::position</parent>.\n"
                "        create a particle in position<local>::position</parent>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /middle and the /inner it implies are both assigned to the particle in
    # <local>::/parent. /inner's independent operation therefore uses that
    # position as its action parent rather than depending on its trigger.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(local)": [],
        "test.create(local::/parent)": ["test.create(local)"],
        "test.create(local::/parent::/middle::trigger_pos)": [
            "test.create(local::/parent)"
        ],
        "middle.create(/inner::trigger_pos)": ["test.create(local::/parent)"],
        "inner.create(scratch)": ["test.create(local::/parent)"],
        "inner.destroy(scratch)": ["inner.create(scratch)"],
    }


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
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }


def test_intermediate_callee_operation_suppresses_only_its_caller_path(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "greatgrandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/greatgrandchild>.\n"
            ),
            "grandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</greatgrandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "sibling.dfn": (
                "define the potential position<my.domain.com:my_lib:/sibling>.\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "        it has the position</sibling>.\n"
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
                "        destroy the particle in position</parent>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the position</parent>.\n"
                "    it also assigns the action</inner>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</parent>::position</child>::position</grandchild>.\n"
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
                "        create a particle in position</parent>::position</child>::position</grandchild>.\n"
                "        create a particle in position</parent>::position</child>::position</grandchild>::position</greatgrandchild>.\n"
                "        create a particle in position</parent>::position</sibling>.\n"
                "        create a particle in action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /middle's grandchild destroy reaches /test's operations on the same path,
    # so /inner's parent destroy needs only /middle's operation for that path.
    # /test's sibling fill is on an independent path and remains a dependency.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/parent::/child::/grandchild)": ["test.create(/parent::/child)"],
        "test.create(/parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(/parent::/child::/grandchild)"
        ],
        "test.create(/parent::/sibling)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.destroy(/parent::/child::/grandchild)": [
            "test.create(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "middle.create(/inner::trigger_pos)": [],
        "inner.destroy(/parent)": [
            "middle.destroy(/parent::/child::/grandchild)",
            "test.create(/parent::/sibling)",
        ],
    }


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
    # middle moves iface (carrying its </parent> child) into inner::input. The
    # move empties iface, which the caller filled a </parent> inside, so it waits
    # on the caller's fill of iface::/parent, not the caller's fill of iface,
    # which that child supersedes. inner then fills the
    # empty-by-default grandchildren parent::/a and parent::/b; each branches from
    # the move that placed the parent, since the move's target (gw::/inner::input)
    # is the nearest ancestor the caller touched.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(mw)": [],
        "test.create(mw::/middle::iface)": ["test.create(mw)"],
        "test.create(mw::/middle::iface::/parent)": ["test.create(mw::/middle::iface)"],
        "test.create(mw::/middle::run)": ["test.create(mw)"],
        "middle.create(gw)": ["test.create(mw)"],
        "middle.move(iface, gw::/inner::input)": [
            "middle.create(gw)",
            "test.create(mw::/middle::iface::/parent)",
        ],
        "middle.create(gw::/inner::run)": ["middle.create(gw)"],
        "inner.create(input::/parent::/a)": ["middle.move(iface, gw::/inner::input)"],
        "inner.create(input::/parent::/b)": ["middle.move(iface, gw::/inner::input)"],
        # The destroy waits on the callee's fills inside gw, which already reach
        # the carrying move, so it needs no direct move edge.
        "middle.destroy(gw)": [
            "middle.create(gw::/inner::run)",
            "inner.create(input::/parent::/a)",
            "inner.create(input::/parent::/b)",
        ],
    }


def test_input_carried_through_two_moves_reaches_the_triggered_inner(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<input>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<input>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<input>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<input> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<middle_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<middle_holder>.\n"
                "        move the particle in position<input> to position<middle_holder>::action</middle>::position<input>.\n"
                "        create a particle in position<middle_holder>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<outer_holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<input>.\n"
                "        create a particle in position<outer_holder>.\n"
                "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
                "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /test fills box::/inner::input, then box is carried by two moves (into /outer
    # then /middle) before /middle fills the trigger and /inner destroys the input
    # that rode along. Each callee operation resolves to the move that most recently
    # carried the particle, not to a trigger.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/inner::input)": ["test.create(box)"],
        "test.create(outer_holder)": [],
        "test.move(box, outer_holder::/outer::input)": [
            "test.create(box::/inner::input)",
            "test.create(outer_holder)",
        ],
        "test.create(outer_holder::/outer::run)": ["test.create(outer_holder)"],
        "outer.create(middle_holder)": ["test.create(outer_holder)"],
        "outer.move(input, middle_holder::/middle::input)": [
            "outer.create(middle_holder)",
            "test.move(box, outer_holder::/outer::input)",
        ],
        "outer.create(middle_holder::/middle::run)": ["outer.create(middle_holder)"],
        "middle.create(input::/inner::run)": [
            "outer.move(input, middle_holder::/middle::input)"
        ],
        "inner.destroy(input)": ["outer.move(input, middle_holder::/middle::input)"],
    }


@pytest.mark.xfail(strict=True, reason=_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS)
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
    assert operation_dependencies(result.operation_graphs) == {
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


def test_caller_consumes_a_nested_guarantee(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out>.\n"
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
                "    define the position<result>.\n"
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
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</middle>::position<gw>::action</inner>::position<out> to position<result>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # middle triggers inner, and inner's <out> propagates to test as a nested
    # guarantee, so test's move consumes an output produced two levels down.
    # The move must wait on inner's final operation on <out>, resolved within
    # the middle instance test triggered.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(out)": ["test.create(box::/middle::gw)"],
        "test.move(box::/middle::gw::/inner::out, result)": ["inner.create(out)"],
    }


@pytest.mark.xfail(strict=True, reason=_EMPTY_RULE_NOT_PRESERVED_ACROSS_ACTIONS)
def test_callee_move_of_a_position_filled_two_levels_up_waits_on_the_caller_child_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<source> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<source> to position<holder>.\n"
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
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<source>.\n"
                "        create a particle in position<box>::action</middle>::position<gw>::action</inner>::position<source>::position</a>.\n"
                "        create a particle in position<box>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /inner empties a position that /middle never touches: /middle only passes the
    # requirement on it up to /test, which filled it and filled the </a> inside it.
    # The move's empty of <source> has to reach across both triggers to find that
    # </a> fill, while its fill of <holder> waits on the /test create of <gw>, the
    # particle <holder> lives in, two levels up.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::source)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::gw::/inner::source::/a)": [
            "test.create(box::/middle::gw::/inner::source)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.move(source, holder)": [
            "test.create(box::/middle::gw::/inner::source::/a)",
        ],
    }


def test_callee_empty_waits_on_a_child_a_guaranteeing_action_filled(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "gc.dfn": "define the potential position<my.domain.com:my_lib:/gc>.\n",
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</gc>.\n"
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
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>::position</child>::position</gc>.\n"
                "    }\n"
                "}\n"
            ),
            "mover.dfn": (
                "define the potential action<my.domain.com:my_lib:/mover> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</gc>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</parent>::position</child> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</parent>.\n"
                "    it also assigns the action</filler>.\n"
                "    it also assigns the action</mover>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>.\n"
                "        create a particle in position</parent>::position</child>.\n"
                "        create a particle in action</filler>::position<trigger_pos>.\n"
                "        create a particle in action</mover>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # /filler and /mover share the implied /parent particle. /filler fills
    # /parent::/child::/gc, which it guarantees rather than /test operating on it
    # directly. /mover then empties /parent::/child, carrying it to <dest>, which
    # requires /gc. Emptying /parent::/child must wait on the operation that filled
    # its /gc child -- /filler's create -- even though no direct /test operation
    # touched it: the fill reaches the move through the guarantee.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/filler::trigger_pos)": [],
        "test.create(/mover::trigger_pos)": [],
        "filler.create(/parent::/child::/gc)": ["test.create(/parent::/child)"],
        "mover.move(/parent::/child, dest)": ["filler.create(/parent::/child::/gc)"],
    }


def test_caller_consumes_a_guarantee_from_two_triggers_down(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<igw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<igw>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<result>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</outer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<gw>.\n"
                "        create a particle in position<box>::action</outer>::position<gw>::action</middle>::position<igw>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</outer>::position<gw>::action</middle>::position<igw>::action</inner>::position<out> to position<result>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # outer never touches inner's <out>, so outer's graph has no guarantee node
    # for it -- only the requirement node at the same key. The guarantee reaches
    # test straight from outer's contract references, and test's move resolves
    # across outer's trigger of middle to inner's final operation on <out>, in
    # the chain of triggers test fired.
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::gw)": ["test.create(box)"],
        "test.create(box::/outer::gw::/middle::igw)": ["test.create(box::/outer::gw)"],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.create(gw::/middle::trigger_pos)": ["test.create(box::/outer::gw)"],
        "middle.create(igw::/inner::trigger_pos)": [
            "test.create(box::/outer::gw::/middle::igw)"
        ],
        # <out> is empty by default under test's fill of <igw>: its EMPTY
        # requirement propagates to test as pass-through RequirementNodes and
        # resolves to that fill.
        "inner.create(out)": ["test.create(box::/outer::gw::/middle::igw)"],
        "test.move(box::/outer::gw::/middle::igw::/inner::out, result)": [
            "inner.create(out)"
        ],
    }
