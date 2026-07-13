from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


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
