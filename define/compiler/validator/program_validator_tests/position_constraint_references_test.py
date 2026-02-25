# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


def test_position_constraint_reference_with_invalid_path():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</Bad>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Bad"
    assert diags[0].char == "B"
    assert diags[0].position.line == 3
    assert diags[0].position.column == 22


def test_same_fqun_constraint_reference_must_use_short_form():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "it may only contain dimension points where {\n"
        "it has the position<my.domain.com:my_lib:/child>.\n"
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
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21


def test_same_fqun_constraint_reference_in_local_position_must_use_short_form():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<my_pos> {\n"
        "it may only contain dimension points where {\n"
        "it has the position<my.domain.com:my_lib:/child>.\n"
        "}\n"
        "}\n"
        "it happens when {\n"
        "} and it does {\n"
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
    assert diags[0].position.column == 21


def test_referenced_global_name_wrong_type_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "target.def").write_text(
        "define the potential action<mv:define-lang.org:test_walk_wrong_type:/target>.\n",
        encoding="utf-8",
    )
    (tmp_path / "test.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_wrong_type:/test> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</target>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    test_helpers.write_project_config(
        tmp_path, "mv:define-lang.org:test_walk_wrong_type"
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diags[0].path == "/target"
    assert diags[0].expected_type == "position"
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
