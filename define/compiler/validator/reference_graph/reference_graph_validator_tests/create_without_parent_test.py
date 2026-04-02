# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_create_in_child_of_unoccupied_local_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<local>::position</x>"
    assert all_diags[0].parent_position_name == "position<local>"


def test_create_in_multilevel_chain_without_parents(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>::position</x>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].position_name == "position<local>::position</x>::position</y>"
    assert all_diags[0].parent_position_name == "position<local>::position</x>"
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].position_name == "position<local>::position</x>::position</y>"
    assert all_diags[1].parent_position_name == "position<local>"


def test_create_in_child_when_parent_occupied_but_grandchild_not(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::position</x>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].position_name == "position<local>::position</x>::position</y>"
    assert all_diags[0].parent_position_name == "position<local>::position</x>"


def test_create_parent_then_child_succeeds(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_interface_position_parent_succeeds(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_position_init_create_self_then_child_succeeds(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_position_init_create_child_without_self_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37
    assert all_diags[0].position_name == "position</test>::position</x>"
    assert all_diags[0].parent_position_name == "position</test>"


def test_unknown_parent_suppresses_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position<local>.\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)


def test_subsequent_create_after_unknown_child_does_not_cascade(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
