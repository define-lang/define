# pyright: reportUnusedCallResult=false

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


def test_valid_local_positions():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_undefined_from_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
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
    assert diags[0].position.line == 5
    assert diags[0].position.column == 46


def test_undefined_to_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    it happens when {\n"
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
    assert diags[0].position.line == 5
    assert diags[0].position.column == 68


def test_both_positions_undefined():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
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
    assert diags[0].position.line == 4
    assert diags[0].position.column == 46
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<bad_to>"
    assert diags[1].position.line == 4
    assert diags[1].position.column == 68


def test_same_fqun_must_use_short_form_in_from():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        move the dimension point in"
        " position<my.domain.com:my_lib:/other> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].position.line == 5
    assert diags[0].position.column == 46


def test_same_fqun_must_use_short_form_in_to():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        move the dimension point in position<from_pos>"
        " to position<my.domain.com:my_lib:/other>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].position.line == 5
    assert diags[0].position.column == 68


def test_move_from_empty_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<from_pos>.\n"
        "define the position<to_pos>.\n"
        "move the dimension point in position<from_pos> to position<to_pos>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<from_pos>"


def test_move_to_occupied_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<from_pos>.\n"
        "define the position<to_pos>.\n"
        "create a dimension point in position<from_pos>.\n"
        "create a dimension point in position<to_pos>.\n"
        "move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[0].position_name == "position<to_pos>"


def test_move_updates_state_allows_create_in_source():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<a>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_move_updates_state_blocks_create_in_dest():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[0].position_name == "position<b>"


def test_double_move():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "define the position<c>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "move the dimension point in position<b> to position<c>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_repeated_move_same_direction():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position_name == "position<b>"


def test_round_trip_move_fails_second_return():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "move the dimension point in position<b> to position<a>.\n"
        "move the dimension point in position<b> to position<a>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<b>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position_name == "position<a>"


def test_two_actions_same_name_one_error_one_clean():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
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
    assert all_diags[0].position.line == 6
    assert all_diags[0].position.column == 37


def test_two_actions_same_name_one_occupied_error_one_clean():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        create a dimension point in position<to_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert all_diags[0].position_name == "position<to_pos>"


def test_two_actions_with_move_same_local_names():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_failed_move_marks_both_positions_unknown():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<a>.\n"
        "create a dimension point in position<b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position_name == "position<b>"


def test_move_to_occupied_marks_both_positions_unknown():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<a>.\n"
        "create a dimension point in position<b>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<a>.\n"
        "create a dimension point in position<b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[0].position_name == "position<b>"


def test_both_from_empty_and_to_occupied_marks_unknown():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "create a dimension point in position<b>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<a>.\n"
        "create a dimension point in position<b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position_name == "position<b>"


def test_unknown_state_does_not_affect_other_positions():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<a>.\n"
        "define the position<b>.\n"
        "define the position<c>.\n"
        "create a dimension point in position<a>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "move the dimension point in position<a> to position<b>.\n"
        "create a dimension point in position<c>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)
    assert diags[1].position_name == "position<b>"


def test_valid_global_to_position(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "test.def").write_text(
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<local_pos>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<local_pos>.\n"
            "        move the dimension point in position<local_pos>"
            " to position</global_pos>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "global_pos.def").write_text(
        "define the potential position<my.domain.com:my_lib:/global_pos>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_move_to_same_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
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
    assert diags[0].position_name == "position<a>"


def test_move_to_same_position_does_not_mark_unknown():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
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
    assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)


def test_move_to_chained_prefix_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "test.def").write_text(
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<local_pos> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</target_pos>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<local_pos>.\n"
            "        move the dimension point in position<local_pos>"
            " to position<local_pos>::position</target_pos>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "target_pos.def").write_text(
        "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert len(test_result.diagnostics) == 1
    assert isinstance(
        test_result.diagnostics[0], diagnostics.MoveIntoDefiningPositionDiagnostic
    )
    assert test_result.diagnostics[0].from_position == "position<local_pos>"
    assert (
        test_result.diagnostics[0].to_position
        == "position<local_pos>::position<my.domain.com:my_lib:/target_pos>"
    )


def test_move_to_chained_prefix_marks_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "test.def").write_text(
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<local_pos> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</target_pos>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<local_pos>.\n"
            "        move the dimension point in position<local_pos>"
            " to position<local_pos>::position</target_pos>.\n"
            "        create a dimension point in position<local_pos>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "target_pos.def").write_text(
        "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert len(test_result.diagnostics) == 1
    assert isinstance(
        test_result.diagnostics[0], diagnostics.MoveIntoDefiningPositionDiagnostic
    )


def test_move_different_first_element_no_prefix_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        define the position<b>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<b>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert diags == []
