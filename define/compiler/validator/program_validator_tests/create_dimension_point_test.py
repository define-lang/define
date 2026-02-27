# pyright: reportUnusedCallResult=false
"""Create dimension point validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


def test_short_form_global_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "test.def").write_text(
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "it happens when {\n"
            "} and it does {\n"
            "create a dimension point in position</other>.\n"
            "}\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "other.def").write_text(
        "define the potential position<my.domain.com:my_lib:/other>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_same_fqun_reference_must_use_short_form():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<my.domain.com:my_lib:/other>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].position.line == 4
    assert diags[0].position.column == 38


def test_valid_local_name():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "define the position<inner_pos>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<inner_pos>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_invalid_local_name_char():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "define the position<inner_pos>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<inner_pos>::position<Bad>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "Bad"
    assert diags[0].char == "B"
    assert diags[0].position.line == 5
    assert diags[0].position.column == 59


def test_chain_both_endpoints_action():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in action<act_a>::position<pos_mid>::action<act_b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.PositionReferenceChainStartDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 36
    assert isinstance(diags[1], diagnostics.PositionReferenceChainEndDiagnostic)
    assert diags[1].position.line == 4
    assert diags[1].position.column == 70


def test_chain_ending_with_action():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<pos_a>::action<act_b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 53


def test_chain_starting_with_action():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in action<act_a>::position<pos_b>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PositionReferenceChainStartDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 36


def test_name_error_with_chain_endpoint_check():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in action<Bad>::position<pos_other>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "Bad"
    assert diags[0].char == "B"
    assert diags[0].position.line == 4
    assert diags[0].position.column == 36
    assert isinstance(diags[1], diagnostics.PositionReferenceChainStartDiagnostic)
    assert diags[1].position.line == 4
    assert diags[1].position.column == 36


def test_single_action_in_position_reference():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in action<act_other>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PositionReferenceChainStartDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 36


def test_valid_chain_with_action_in_middle():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<pos_a>::action<act_b>::position<pos_c>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert results[0].diagnostics == []


def test_cross_universe_not_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "create a dimension point in position<other.domain.com:other_lib:/dep>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "other.domain.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].position.line == 4
    assert diags[0].position.column == 38
