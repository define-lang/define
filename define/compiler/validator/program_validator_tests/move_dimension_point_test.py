# pyright: reportUnusedCallResult=false

# TOOD: Break up this test.
# TODO: Improve the assertions in this test.

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.program_validator_tests.conftest import ValidateProject


def test_valid_local_positions():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "        the position<from_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_duplicate_source_definition_does_not_add_move_constraint_diagnostics(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position</dest>.\n"
                "    }\n"
                "}\n"
            ),
            "dest.def": (
                "define the potential position<my.domain.com:my_lib:/dest> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</required>.\n"
                "    }\n"
                "}\n"
            ),
            "required.def": (
                "define the potential action<my.domain.com:my_lib:/required>.\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "action"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].position.line == 8
    assert all_diags[0].position.column == 1


def test_undefined_from_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "        the position<to_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<no_such_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46


def test_undefined_to_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    it happens when {\n"
        "        the position<from_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<from_pos>"
        " to position<no_such_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 68


def test_both_positions_undefined():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<bad_from>"
        " to position<bad_to>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<bad_from>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<bad_to>"
    assert diags[1].position.line == 6
    assert diags[1].position.column == 68


def test_same_fqun_must_use_short_form_in_from(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<to_pos>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<my.domain.com:my_lib:/other> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].position.line == 7
    assert all_diags[0].position.column == 46


def test_same_fqun_must_use_short_form_in_to(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<my.domain.com:my_lib:/other>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].position.line == 7
    assert all_diags[0].position.column == 68
    assert isinstance(all_diags[1], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[1].position.line == 7
    assert all_diags[1].position.column == 37
    assert all_diags[1].position_name == "position<from_pos>"


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
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


def test_valid_global_to_position(validate_project: ValidateProject):
    results = validate_project(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos>.\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position</global_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "global_pos.def": "define the potential position<my.domain.com:my_lib:/global_pos>.\n",
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_from_a_position_to_itself():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].position.line == 8
    assert diags[0].position.column == 52
    assert diags[0].position_name == "position<a>"


def test_move_from_a_chained_position_to_itself(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x> to position<a>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert all_diags[0].position.line == 12
    assert all_diags[0].position.column == 79
    assert all_diags[0].position_name == "position<a>::position</x>"


def test_move_to_same_position_does_not_mark_unknown():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].position.line == 8
    assert diags[0].position.column == 52
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position.line == 9
    assert diags[1].position.column == 37
    assert diags[1].position_name == "position<a>"
    assert diags[1].first_creation_line == 7


def test_move_to_chained_prefix_position(validate_project: ValidateProject):
    results = validate_project(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.def": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].position.line == 10
    assert all_diags[0].position.column == 81
    assert all_diags[0].from_position == "position<local_pos>"
    assert all_diags[0].to_position == "position<local_pos>::position</target_pos>"


def test_move_to_chained_prefix_marks_unknown(validate_project: ValidateProject):
    results = validate_project(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "        create a dimension point in position<local_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.def": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].position.line == 10
    assert all_diags[0].position.column == 81
    assert all_diags[0].from_position == "position<local_pos>"
    assert all_diags[0].to_position == "position<local_pos>::position</target_pos>"


def test_move_violates_dest_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_from_unconstrained_to_constrained(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 13
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_with_compatible_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_local_move_round_trip_with_constraint_subset(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "b.def": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "c.def": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "d.def": "define the potential position<my.domain.com:my_lib:/d>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</b>.\n"
                "                it has the position</c>.\n"
                "                it has the position</d>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</b>.\n"
                "                it has the position</c>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>.\n"
                "        move the dimension point in position<b> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_local_move_violates_constraints_marks_unknown(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "        create a dimension point in position<from_pos>.\n"
                "        create a dimension point in position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_to_unconstrained_position(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos>.\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_definition_local_to_statement_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<def_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<def_pos> to position<stmt_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 15
    assert all_diags[0].position.column == 58
    assert all_diags[0].from_position == "position<def_pos>"
    assert all_diags[0].to_position == "position<stmt_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_definition_local_to_statement_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<def_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<def_pos> to position<stmt_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_statement_local_to_definition_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<stmt_pos>.\n"
                "        move the dimension point in position<stmt_pos> to position<def_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_statement_local_to_definition_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<stmt_pos>.\n"
                "        move the dimension point in position<stmt_pos> to position<def_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_definition_local_to_definition_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<to_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_definition_local_to_definition_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<to_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_to_chained_dest_violates_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            # TODO: This should be failing because there is no DP in position<dest>.
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_to_chained_dest_satisfies_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_to_chained_dest_unconstrained(validate_project: ValidateProject):
    results = validate_project(
        {
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_from_chained_to_local_violates_constraints(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_from_chained_to_local_satisfies_constraints(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "q.def": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_from_unconstrained_local_to_chained_constrained(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_violates(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_satisfies(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_chained_to_definition_local_violates(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_chained_to_definition_local_satisfies(validate_project: ValidateProject):
    results = validate_project(
        {
            "q.def": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_from_multi_element_chain_to_unconstrained_local(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
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
                "        define the position<a>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_from_multi_element_chain_to_constrained_local(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</z>.\n"
                "    }\n"
                "}\n"
            ),
            "z.def": "define the potential position<my.domain.com:my_lib:/z>.\n",
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
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_three_element_chain_to_three_element_chain_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.def": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x>::position</y> to position<b>::position</z>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_three_element_chain_to_three_element_chain_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.def": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</w>.\n"
                "    }\n"
                "}\n"
            ),
            "w.def": (
                "define the potential position<my.domain.com:my_lib:/w> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x>::position</y> to position<b>::position</z>::position</w>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].from_position == "position<a>::position</x>::position</y>"
    assert all_diags[0].to_position == "position<b>::position</z>::position</w>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


# --- Cross-FQUN move tests ---

_PARENT = "mv:define-lang.org:parent"
_CHILD = "mv:define-lang.org:child"


def _write_source(tmp_path: Path, rel_path: str, source: str) -> None:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _setup_cross_fqun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_helpers.write_project_config(tmp_path, _PARENT)
    test_helpers.write_local_deps_config(tmp_path, {_CHILD: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD)
    monkeypatch.chdir(tmp_path)


def test_cross_fqun_local_to_local_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<to_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_local_to_local_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<to_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_local_to_chained_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_local_to_chained_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos>.\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_chained_to_local_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<src> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<src>.\n"
            f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_chained_to_local_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<src> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<src>.\n"
            f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_move_from_local_local_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    it happens when {\n"
        "        the position<a> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<a>::position<b> to position<c>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert len(results[0].diagnostics) == 2
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    )


def test_move_from_local_local_local_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    define the position<d>.\n"
        "    it happens when {\n"
        "        the position<a> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<a>::position<b>::position<c> to position<d>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert len(results[0].diagnostics) == 3
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[2],
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    )
