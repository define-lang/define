# pyright: reportUnusedCallResult=false
"""Shared validator fixtures for program_validator_tests."""

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Protocol, overload

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator, validation_result
from define.compiler.validator.program_validator_tests import test_helpers

type ParseAndValidateFile = Callable[[str | bytes], validation_result.ValidationResult]
_DEFAULT_RELATIVE_PATH = PurePosixPath("path.def")


class ValidateSourceAsFile(Protocol):
    """Callable that validates source as a file and returns diagnostics."""

    @overload
    def __call__(
        self,
        source: str,
        expected_universe_name: str,
    ) -> list[diagnostics.Diagnostic]: ...

    @overload
    def __call__(
        self,
        source: str,
        expected_universe_name: str,
        relative_path: PurePosixPath,
    ) -> list[diagnostics.Diagnostic]: ...


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
        results = program_validator.ProgramValidator().validate_program(relative_path)
        assert len(results) == 1
        return results[0]

    return _run


@pytest.fixture
def validate_source_as_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateSourceAsFile:
    """Validate one source string as a file and return diagnostics."""

    def _run(
        source: str,
        expected_universe_name: str,
        relative_path: PurePosixPath = _DEFAULT_RELATIVE_PATH,
    ) -> list[diagnostics.Diagnostic]:
        source_path = tmp_path / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8")
        test_helpers.write_project_config(tmp_path, expected_universe_name)
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(relative_path)
        assert len(results) == 1
        return results[0].diagnostics

    return _run
