# pyright: reportUnusedCallResult=false
"""Dimension point conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def test_duplicate_local_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
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
    assert diags[0].position_name == "position<my_pos>"
    assert diags[0].first_creation_line == 7
    assert diags[0].position.line == 8
    assert diags[0].position.column == 37


def test_different_local_positions():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<pos_a>.\n"
        "        define the position<pos_b>.\n"
        "        create a dimension point in position<pos_a>.\n"
        "        create a dimension point in position<pos_b>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_undefined_position_not_tracked_for_duplicates():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<no_such_pos>.\n"
        "        create a dimension point in position<no_such_pos>.\n"
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
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<no_such_pos>"
    assert diags[1].position.line == 7
    assert diags[1].position.column == 46


def test_two_actions_same_local_position_create_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_two_actions_same_name_one_duplicate_one_clean():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a dimension point in position<my_pos>.\n"
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
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<my_pos>"
    assert all_diags[0].first_creation_line == 7
    assert all_diags[0].position.line == 8
    assert all_diags[0].position.column == 37


def test_three_actions_dimension_point_isolation():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a dimension point in position<shared_name>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a dimension point in position<shared_name>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_three> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a dimension point in position<shared_name>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_definition_block_position_enforced():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<outer_pos>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<outer_pos>.\n"
        "        create a dimension point in position<outer_pos>.\n"
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
    assert diags[0].position_name == "position<outer_pos>"
    assert diags[0].first_creation_line == 7
    assert diags[0].position.line == 8
    assert diags[0].position.column == 37
