# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.conftest import ValidateNonFilesystemWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_move_from_empty_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<from_pos>"


def test_move_to_occupied_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        create a dimension point in position<to_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 59
    assert diags[0].position_name == "position<to_pos>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 37
    assert diags[0].occupied_at.line == 9


def test_move_updates_state_allows_create_in_source(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_cannot_create_in_position_that_was_moved_into(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<b>"
    assert diags[0].created_at.line == 9


def test_double_move_works(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        define the position<c>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        move the dimension point in position<b> to position<c>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_same_move_twice_in_a_row(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 10
    assert diags[1].location.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 52
    assert diags[1].occupied_at.line == 9


def test_round_trip_move_fails_second_return(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        move the dimension point in position<b> to position<a>.\n"
        "        move the dimension point in position<b> to position<a>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<b>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 11
    assert diags[1].location.column == 52
    assert diags[1].position_name == "position<a>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 52
    assert diags[1].occupied_at.line == 10


def test_two_actions_same_name_one_empty_error_one_clean(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position<from_pos>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 37


def test_two_actions_same_name_one_occupied_error_one_clean(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        create a dimension point in position<to_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 59
    assert all_diags[0].position_name == "position<to_pos>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.column == 37
    assert all_diags[0].occupied_at.line == 9


def test_two_actions_with_move_same_local_names(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_move_from_empty_marks_both_positions_unknown(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        create a dimension point in position<b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<a>"


def test_move_to_occupied_marks_both_positions_unknown(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        create a dimension point in position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        create a dimension point in position<b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 52
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 37
    assert diags[0].occupied_at.line == 9


def test_both_from_empty_and_to_occupied_marks_unknown(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        create a dimension point in position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 9
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 9
    assert diags[1].location.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 37
    assert diags[1].occupied_at.line == 8


def test_unknown_state_does_not_affect_other_positions(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        define the position<c>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        create a dimension point in position<c>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 11
    assert diags[1].location.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 52
    assert diags[1].occupied_at.line == 10


def test_single_unknown_position_marks_both_unknown(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        define the position<c>.\n"
        "        create a dimension point in position<a>.\n"
        "        create a dimension point in position<b>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "        move the dimension point in position<a> to position<c>.\n"
        "        create a dimension point in position<c>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 52
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 37
    assert diags[0].occupied_at.line == 10


def test_move_from_chained_to_occupied_local_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<src>::position</x>.\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 68
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.column == 37
    assert all_diags[0].occupied_at.line == 14


def test_move_from_empty_local_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<src>::position</x>"


def test_move_to_occupied_local_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<dest>.\n"
                "        create a dimension point in position<dest>::position</x>.\n"
                "        move the dimension point in position<src> to position<dest>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 54
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<dest>::position</x>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 14
    assert all_diags[0].occupied_at.column == 37
    assert all_diags[0].occupied_at.file_path == PurePosixPath("test.dfn")


def test_double_move_from_local_chained_fails(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest_a>.\n"
                "        define the position<dest_b>.\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<src>::position</x>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest_a>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<src>::position</x>"


def test_move_from_local_chained_to_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<src>::position</x>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_local_to_local_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
                "        define the position<src>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<src> to position<dest>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_between_local_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<src>::position</x>.\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
