# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ParseAndValidateFile,
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_create_in_self(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</test>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert diags == []


def test_create_in_self_with_constraints(
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
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_local_to_self(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        define the position<local>.\n"
        "        create a dimension point in position<local>.\n"
        "        move the dimension point in position<local> to position</test>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert diags == []


def test_move_from_self_to_local(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        define the position<local>.\n"
        "        create a dimension point in position</test>.\n"
        "        move the dimension point in position</test> to position<local>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert diags == []


def test_move_to_self_violates_constraints(
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
                "        define the position<local>.\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position</test>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 56
    assert all_diags[0].source_position == "position<local>"
    assert all_diags[0].target_position == "position</test>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_from_self_violates_constraints(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position</test>.\n"
                "        move the dimension point in position</test> to position<local>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 56
    assert all_diags[0].source_position == "position</test>"
    assert all_diags[0].target_position == "position<local>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_self_reference_mixed_with_other_reference(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</other>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "position</other>"
    assert all_diags[0].full_global_name == "position<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 37


def test_chained_name_starting_with_self_two_items_valid(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::position</other>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_chained_name_starting_with_self_two_items_invalid_global(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>::position</other>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert all_diags[0].location.line == 3
    assert all_diags[0].location.column == 54
    assert all_diags[0].element_name == "position<my.domain.com:my_lib:/other>"
    assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/test>"


def test_chained_name_starting_with_self_two_items_invalid_local(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</test>::position<inner>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 54
    assert diags[0].local_name == "position<inner>"
    assert diags[0].preceding_name == "position<my.domain.com:my_lib:/test>"
    assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert diags[1].location.line == 3
    assert diags[1].location.column == 54
    assert diags[1].element_name == "position<inner>"
    assert diags[1].parent_name == "position<my.domain.com:my_lib:/test>"


def test_chained_name_starting_with_self_three_items_valid(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<local>.\n"
                "    it happens when {\n"
                "        the position<local> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::action</other>::position<local>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_chained_name_starting_with_self_three_items_invalid(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<local>.\n"
                "    it happens when {\n"
                "        the position<local> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>::action</other>::position<nonexistent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert len(result.program_result.file_results) == 2
    assert result.program_result.file_results[0].file_path == PurePosixPath("test.dfn")
    test_diags = result.program_result.file_results[0].diagnostics
    assert len(test_diags) == 1
    assert isinstance(test_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
    assert test_diags[0].location.line == 6
    assert test_diags[0].location.column == 70
    assert test_diags[0].element_name == "position<nonexistent>"
    assert test_diags[0].parent_name == "action<my.domain.com:my_lib:/other>"


def test_self_reference_does_not_trigger_file_loading(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</test>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    assert len(results) == 1
    diags = results[0].diagnostics
    assert diags == []


def test_self_reference_in_constraint_block_is_still_circular(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</test>.\n"
        "    }\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</test>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
