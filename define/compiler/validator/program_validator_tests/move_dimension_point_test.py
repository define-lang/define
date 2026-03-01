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
