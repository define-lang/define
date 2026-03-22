# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.structural import program_validator


def test_move_from_empty_position():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 8
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<from_pos>"


def test_move_to_occupied_position():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].position.line == 10
    assert diags[0].position.column == 59
    assert diags[0].position_name == "position<to_pos>"
    assert diags[0].occupied_at_line == 9


def test_move_updates_state_allows_create_in_source():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_cannot_create_in_position_that_was_moved_into():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position.line == 10
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<b>"
    assert diags[0].first_creation_line == 9


def test_double_move_works():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_same_move_twice_in_a_row():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 10
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].position.line == 10
    assert diags[1].position.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at_line == 9


def test_round_trip_move_fails_second_return():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 11
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<b>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].position.line == 11
    assert diags[1].position.column == 52
    assert diags[1].position_name == "position<a>"
    assert diags[1].occupied_at_line == 10


def test_two_actions_same_name_one_empty_error_one_clean():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position<from_pos>"
    assert all_diags[0].position.line == 8
    assert all_diags[0].position.column == 37


def test_two_actions_same_name_one_occupied_error_one_clean():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].position.line == 10
    assert all_diags[0].position.column == 59
    assert all_diags[0].position_name == "position<to_pos>"
    assert all_diags[0].occupied_at_line == 9


def test_two_actions_with_move_same_local_names():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_move_from_empty_marks_both_positions_unknown():
    """Proves that later errors don't fire after an earlier dimension point state error."""
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 8
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<a>"


def test_move_to_occupied_marks_both_positions_unknown():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].position.line == 10
    assert diags[0].position.column == 52
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at_line == 9


def test_both_from_empty_and_to_occupied_marks_unknown():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 9
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].position.line == 9
    assert diags[1].position.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at_line == 8


def test_unknown_state_does_not_affect_other_positions():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position.line == 11
    assert diags[0].position.column == 37
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].position.line == 11
    assert diags[1].position.column == 52
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at_line == 10


def test_single_unknown_position_marks_both_unknown():
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
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].position.line == 11
    assert diags[0].position.column == 52
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at_line == 10


def test_move_from_chained_to_occupied_local_position(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
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
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<src>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].position.line == 14
    assert all_diags[0].position.column == 68
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].occupied_at_line == 13
