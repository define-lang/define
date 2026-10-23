"""Helpers for tests that structurally validate a single-file program."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from define.compiler.validator import validation_result


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
        _ = source_path.write_text(source, encoding="utf-8", newline="\n")
    else:
        _ = source_path.write_bytes(source)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    return results[0]
