# pyright: reportUnusedCallResult=false
"""Shared validator fixtures for validator_tests."""

from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import validation_result, validator
from define.compiler.validator_tests import test_helpers

type ParseAndValidateFile = Callable[[str | bytes], validation_result.ValidationResult]


@pytest.fixture
def parse_and_validate_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ParseAndValidateFile:
    """Parse and validate a single source string as a file in a temp project."""

    def _run(source: str | bytes) -> validation_result.ValidationResult:
        relative_path = PurePosixPath("test.def")
        source_path = tmp_path / relative_path
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        if isinstance(source, str):
            source_path.write_text(source, encoding="utf-8")
        else:
            source_path.write_bytes(source)
        monkeypatch.chdir(tmp_path)
        results = validator.Validator().parse_and_validate_program(relative_path)
        assert len(results) == 1
        return results[0]

    return _run
