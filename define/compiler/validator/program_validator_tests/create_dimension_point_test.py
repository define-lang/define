# pyright: reportUnusedCallResult=false
"""Create dimension point validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.structural import program_validator


def test_short_form_global_reference(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": "define the potential position<my.domain.com:my_lib:/other>.\n",
        }
    )
    assert not result.has_errors()


def test_same_fqun_reference_must_use_short_form():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<my.domain.com:my_lib:/other>.\n"
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
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46


def test_valid_local_name():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<inner_pos>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<inner_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_cross_universe_not_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<other.domain.com:other_lib:/dep>.\n"
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
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "other.domain.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46


def test_undefined_local_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
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
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46


def test_local_position_defined_after_use():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<later_pos>.\n"
        "        define the position<later_pos>.\n"
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
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<later_pos>"
    assert diags[0].position.line == 6
    assert diags[0].position.column == 46


def test_local_position_defined_in_action_statements_before_use():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<stmt_pos>.\n"
        "        create a dimension point in position<stmt_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_two_actions_with_definition_block_local_positions():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<inner_pos>.\n"
        "        create a dimension point in position<inner_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<inner_pos>.\n"
        "        create a dimension point in position<inner_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors()


def test_single_action_in_position_reference():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in action<act_other>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    diags = result.file_results[0].diagnostics
    assert len(diags) == 3
    assert isinstance(diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
    assert diags[0].position.line == 6
    assert diags[0].position.column == 37
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "action<act_other>"
    assert diags[1].position.line == 6
    assert diags[1].position.column == 44
    assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
    assert diags[2].local_name == "act_other"
    assert diags[2].position.line == 6
    assert diags[2].position.column == 44
