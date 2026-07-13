from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


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


def test_retriggered_action_resolves_both_triggers_to_the_one_parent_fill(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "maker.dfn": (
                "define the potential action<my.domain.com:my_lib:/maker> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<held> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<held>::position</c>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<gw> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</maker>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gw>.\n"
                "        create a particle in position<gw>::action</maker>::position<held>.\n"
                "        create a particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "        destroy the particle in position<gw>::action</maker>::position<held>::position</c>.\n"
                "        destroy the particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "        create a particle in position<gw>::action</maker>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The caller fills <held> once and it serves both invocations: each
    # invocation's create waits on that one fill for its OCCUPIED <held>
    # requirement. The EMPTY requirement on <held>::/c is satisfied by default
    # in the first invocation (its RequirementNode falls through to the parent
    # fill) and by the caller's destroy in the second -- and that destroy
    # waits on the first invocation's create, so the two invocations' writes
    # to <held>::/c cannot race.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/maker::held)": ["test.create(gw)"],
        "test.create(gw::/maker::trigger_pos)": ["test.create(gw)"],
        "maker.create(held::/c)": ["test.create(gw::/maker::held)"],
        "test.destroy(gw::/maker::held::/c)": ["maker.create(held::/c)"],
        "test.destroy(gw::/maker::trigger_pos)": [
            "test.create(gw::/maker::trigger_pos)"
        ],
        "test.create(gw::/maker::trigger_pos)#2": [
            "test.destroy(gw::/maker::trigger_pos)"
        ],
        "maker.create(held::/c)#2": ["test.destroy(gw::/maker::held::/c)"],
    }


def test_retriggered_action_with_no_guarantees_runs_once_per_trigger(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "worker.dfn": (
                "define the potential action<my.domain.com:my_lib:/worker> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<scratch>.\n"
                "        create a particle in position<scratch>.\n"
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
                "        create a particle in position<gw>::action</worker>::position<trigger_pos>.\n"
                "        destroy the particle in position<gw>::action</worker>::position<trigger_pos>.\n"
                "        create a particle in position<gw>::action</worker>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # worker guarantees nothing, so each of its two triggers leaves no
    # GuaranteeNode -- only the two distinct trigger fills. Each instance's
    # operations wait on their own fill.
    assert operation_dependencies(result.program_result, _TEST) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::trigger_pos)": ["test.create(gw)"],
        "test.destroy(gw::/worker::trigger_pos)": [
            "test.create(gw::/worker::trigger_pos)"
        ],
        "test.create(gw::/worker::trigger_pos)#2": [
            "test.destroy(gw::/worker::trigger_pos)"
        ],
        "worker.create(scratch)": ["test.create(gw::/worker::trigger_pos)"],
        "worker.destroy(scratch)": ["worker.create(scratch)"],
        "worker.create(scratch)#2": ["test.create(gw::/worker::trigger_pos)#2"],
        "worker.destroy(scratch)#2": ["worker.create(scratch)#2"],
    }
