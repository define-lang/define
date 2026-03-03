# pyright: reportUnusedCallResult=false
"""Dimension point conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator import program_validator


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert all(isinstance(d, diagnostics.UndefinedLocalNameDiagnostic) for d in diags)


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.LocalDuplicateDimensionPointDiagnostic)
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_definition_block_position_not_enforced():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<outer_pos>.\n"
        "    it happens when {\n"
        "        the position<outer_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<outer_pos>.\n"
        "        create a dimension point in position<outer_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []
