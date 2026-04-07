# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_valid_destroy_local_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<target>.\n"
        "        create a dimension point in position<target>.\n"
        "        destroy the dimension point in position<target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_destroy_chained_name_not_in_constraints(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<x> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</correct>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<x> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<x>::action</wrong>::position<end>.\n"
                "    }\n"
                "}\n"
            ),
            "correct.dfn": (
                "define the potential action<my.domain.com:my_lib:/correct> {\n"
                "    define the position<end>.\n"
                "    it happens when {\n"
                "        the position<end> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong.dfn": (
                "define the potential action<my.domain.com:my_lib:/wrong> {\n"
                "    define the position<end>.\n"
                "    it happens when {\n"
                "        the position<end> has a dimension point.\n"
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
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
    assert all_diags[0].parent_name == "position<x>"


def test_destroy_chained_name_not_in_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pos_a> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<pos_a>::action</child>::position<no_such>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<pos_end>.\n"
                "    it happens when {\n"
                "        the position<pos_end> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/child>"
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 73
