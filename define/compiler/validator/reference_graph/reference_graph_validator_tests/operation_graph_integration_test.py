from define.compiler import conftest
from define.compiler.validator.reference_graph.test_helpers import (
    flatten_operation_graph,
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
    assert flatten_operation_graph(graph, _TEST) == ["test.create(item)"]
