# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_create_in_interface_produces_occupied_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_destroy_in_interface_produces_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_move_between_interfaces_produces_empty_and_moved_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<source>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<source>"
    assert isinstance(
        all_diags[1],
        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic,
    )
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 57
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<dest>"
    assert all_diags[1].origin_name == "position<source>"


def test_destroy_implied_quality_produces_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position</marker>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</marker>"


def test_local_only_destructor_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)


def test_move_out_and_back_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the dimension point in position<item> to position<_holder>.\n"
                "        move the dimension point in position<_holder> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)


def test_create_then_move_out_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<_holder>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
