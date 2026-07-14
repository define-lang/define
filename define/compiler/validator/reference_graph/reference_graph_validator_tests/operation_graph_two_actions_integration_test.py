from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.reference_graph.operation_graph_renderer_new import (
    operation_dependencies_new,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


def test_triggered_action_destroys_its_own_trigger_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    """The simplest possible cross-action test, since an occupied requirement is simpler than an empty one."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
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
    assert operation_dependencies_new(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
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


def test_callee_fill_of_a_child_waits_only_on_the_caller_fill_of_its_parent(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>::position</a>.\n"
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
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # output::/a is empty by default, so the caller never touches it. The callee's
    # fill of it only needs output present, so it waits on the caller's fill of
    # output alone.
    assert operation_dependencies_new(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output::/a)": ["test.create(gateway::/other::output)"],
    }


def test_callee_fill_of_a_child_waits_on_the_caller_destroy_that_emptied_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>::position</a>.\n"
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
                "        create a particle in position<gateway>::action</other>::position<output>::position</a>.\n"
                "        destroy the particle in position<gateway>::action</other>::position<output>::position</a>.\n"
                "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # The caller fills output and then empties output::/a itself, so the callee's
    # fill of output::/a waits on that destroy. The create of the parent only
    # satisfies an empty requirement that nothing else emptied, so it must not be
    # what this one resolves to.
    assert operation_dependencies_new(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::output::/a)": [
            "test.create(gateway::/other::output)"
        ],
        "test.destroy(gateway::/other::output::/a)": [
            "test.create(gateway::/other::output::/a)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output::/a)": ["test.destroy(gateway::/other::output::/a)"],
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
    # trigger. The caller's refill then waits on the callee's destroy, its final
    # operation on the position.
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
    assert operation_dependencies_new(result.operation_graphs) == {
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
            "test.create(gw::/worker::in)",
            "test.destroy(gw::/worker::out)",
        ],
    }


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
            "test.create(gw::/worker::in)",
            "test.create(gw::/worker::box)",
        ],
    }


def test_triggered_action_with_no_guarantees_still_runs(
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
                "    define the position<note>.\n"
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
                "        create a particle in position<note>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    # worker touches only a block-local position, so it guarantees nothing to
    # its caller -- but it still runs. Its operations must appear, waiting on
    # the trigger fill (the scratch destroy is the block-end auto-destruction),
    # and the caller's unrelated create of <note> stays independent of it.
    assert operation_dependencies_new(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::trigger_pos)": ["test.create(gw)"],
        "worker.create(scratch)": ["test.create(gw::/worker::trigger_pos)"],
        "worker.destroy(scratch)": ["worker.create(scratch)"],
        "test.create(note)": [],
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
