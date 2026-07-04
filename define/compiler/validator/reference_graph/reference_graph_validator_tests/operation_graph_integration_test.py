from define.compiler import conftest
from define.compiler.validator.reference_graph.test_helpers import (
    operation_dependencies,
    operation_graph_for,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
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
    graph = operation_graph_for(result.program_result, _TEST)
    assert operation_dependencies(graph, _TEST) == {
        "test.create(box)": [],
        "test.create(box::/a)": ["test.create(box)"],
        "test.create(box::/b)": ["test.create(box)"],
        "test.destroy(box)": [
            "test.create(box)",
            "test.create(box::/a)",
            "test.create(box::/b)",
        ],
    }
