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
