# pyright: reportUnusedCallResult=false
"""Shared validator fixtures for program_validator_tests."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol, overload

import pytest

from define.compiler import action_call_graph, diagnostics
from define.compiler.validator import program_validator, validation_result
from define.compiler.validator.program_validator_tests import test_helpers

type ParseAndValidateFile = Callable[[str | bytes], validation_result.ValidationResult]
_DEFAULT_RELATIVE_PATH = PurePosixPath("path.def")


@dataclass
class ProjectResult:
    """Validation results and call graph from a multi-file project."""

    results: list[validation_result.ValidationResult]
    graph: action_call_graph.ActionCallGraph

    @property
    def all_diagnostics(self) -> list[object]:
        """All diagnostics from all file results."""
        return [d for r in self.results for d in r.diagnostics]

    def result_for(self, suffix: str) -> validation_result.ValidationResult:
        """Return the result whose file path ends with the given suffix."""
        return next(r for r in self.results if str(r.file_path).endswith(suffix))


class ValidateProject(Protocol):
    """Callable that validates a multi-file project and returns results."""

    def __call__(
        self,
        files: dict[str, str],
        *,
        universe_name: str = ...,
    ) -> list[validation_result.ValidationResult]:
        """Validate a project with the given files."""
        ...


class ValidateProjectWithGraph(Protocol):
    """Callable that validates a multi-file project and returns results + graph."""

    def __call__(
        self,
        files: dict[str, str],
        *,
        universe_name: str = ...,
    ) -> ProjectResult:
        """Validate a project with the given files."""
        ...


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


def _run_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    universe_name: str,
) -> ProjectResult:
    test_helpers.write_project_config(tmp_path, universe_name)
    for name, content in files.items():
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    pv = program_validator.ProgramValidator()
    results = pv.validate_program(PurePosixPath("test.def"))
    return ProjectResult(results=results, graph=pv.action_call_graph)


@pytest.fixture
def validate_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateProject:
    """Set up a multi-file project in a temp dir and validate it."""

    def _run(
        files: dict[str, str],
        *,
        universe_name: str = "my.domain.com:my_lib",
    ) -> list[validation_result.ValidationResult]:
        return _run_validation(tmp_path, monkeypatch, files, universe_name).results

    return _run


@pytest.fixture
def validate_project_with_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateProjectWithGraph:
    """Set up a multi-file project and return results + call graph."""

    def _run(
        files: dict[str, str],
        *,
        universe_name: str = "my.domain.com:my_lib",
    ) -> ProjectResult:
        return _run_validation(tmp_path, monkeypatch, files, universe_name)

    return _run


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
