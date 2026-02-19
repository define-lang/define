# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, validator
from define.compiler.validator_tests import test_helpers
from define.compiler.validator_tests.conftest import ParseAndValidateFile


def test_self_cycle_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</test>.\n"
        "}\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<my.domain.com:my_lib:/test>\n"
        + "  --> position<my.domain.com:my_lib:/test>"
    )


def test_two_file_cycle_emits_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "test.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_cycle:/test> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</loop>.\n"
            + "}\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "loop.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_cycle:/loop> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</test>.\n"
            + "}\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    test_helpers.write_project_config(tmp_path, "mv:define-lang.org:test_walk_cycle")
    monkeypatch.chdir(tmp_path)
    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert results[0].diagnostics == []
    assert results[1].file_path == PurePosixPath("loop.def")
    assert results[1].exception is None
    diags = results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<mv:define-lang.org:test_walk_cycle:/test>",
        "position<mv:define-lang.org:test_walk_cycle:/loop>",
        "position<mv:define-lang.org:test_walk_cycle:/test>",
    ]
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<mv:define-lang.org:test_walk_cycle:/test>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/loop>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/test>"
    )
