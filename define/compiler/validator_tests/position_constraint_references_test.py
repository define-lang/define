# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, validator
from define.compiler.validator_tests import test_helpers
from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_position_constraint_reference_with_invalid_path():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</Bad>.\n"
        "}\n"
        "}\n"
    )
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
    results = validator.Validator().parse_and_validate_program(
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
