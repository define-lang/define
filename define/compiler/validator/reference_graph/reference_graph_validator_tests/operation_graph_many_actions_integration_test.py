import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.reference_graph.operation_graph_renderer_new import (
    operation_dependencies_new,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"

_UNTOUCHED_INTERMEDIATE_GUARANTEES_NOT_CROSSED = (
    "an action that never touches a position it passes along from an action it"
    " triggers has no guarantee node for it in its own graph, only the"
    " requirement node at the same key, so a consumer resolves the position to"
    " its state before the trigger rather than to the nested action's final"
    " operation on it"
)


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
    assert operation_dependencies(result.program_result, _TEST) == {
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
    assert operation_dependencies(result.program_result, _TEST) == {
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
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/inner::input)": ["test.create(box)"],
        "test.create(outer_holder)": [],
        "test.move(box, outer_holder::/outer::input)": [
            "test.create(box::/inner::input)",
            "test.create(outer_holder)",
        ],
        "test.create(outer_holder::/outer::run)": ["test.create(outer_holder)"],
        "outer.create(middle_holder)": ["test.create(outer_holder::/outer::run)"],
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
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(out)": ["test.create(box::/middle::gw)"],
        "test.move(box::/middle::gw::/inner::out, result)": ["inner.create(out)"],
    }


@pytest.mark.xfail(strict=True, reason=_UNTOUCHED_INTERMEDIATE_GUARANTEES_NOT_CROSSED)
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
