# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.program_validator_tests.conftest import (
    ParseAndValidateFile,
)


def test_entrypoint_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("nonexistent.def")
    )
    assert len(results) == 1
    assert isinstance(results[0].exception, exceptions.SourceFileNotFoundError)
    assert results[0].diagnostics == []


def test_referenced_file_not_found(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</missing>.\n"
        "}\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "missing.def"
    assert diag.position.line == 3
    assert diag.position.column == 21
