# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateProjectWithReferenceGraph,
)


def test_non_self_ref_global_in_action_body(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</other>::position<x>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<x>.\n"
                "    it happens when {\n"
                "        the position<x> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37


def test_non_self_ref_global_in_position_init(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 3
    assert all_diags[0].location.column == 37


def test_constraint_does_not_make_global_available_as_chain_start(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37


def test_self_reference_in_position_init_is_valid(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert not result.program_result.has_errors()
