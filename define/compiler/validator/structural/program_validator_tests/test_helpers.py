"""Helpers for tests that structurally validate a single-file program."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import parser
from define.compiler.validator import test_helpers, validation_result
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    import pytest

_PARSER = parser.Parser()


def parse_and_validate_file(
    source: str | bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> validation_result.FileValidationResult:
    """Write source as the program's only file and structurally validate it."""
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    if isinstance(source, str):
        _ = source_path.write_text(source, encoding="utf-8")
    else:
        _ = source_path.write_bytes(source)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator(_PARSER)
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    return results[0]
