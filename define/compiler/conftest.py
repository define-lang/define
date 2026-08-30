# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false
"""Shared test fixtures for the Define compiler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Protocol, cast

import pytest

from define.compiler import parser
from define.compiler.validator import test_helpers, validation_result
from define.compiler.validator.reference_graph import (
    operation_graph,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator
from define.testdata import path_resolver

if TYPE_CHECKING:
    from define.compiler.graphs import action_call_graph

_PARSER = parser.Parser()


@dataclass
class FullValidationResult:
    """Result of running both structural and reference graph validation."""

    program_result: validation_result.ProgramValidationResult
    reference_graph_result: reference_graph_validator.ReferenceGraphValidationResult

    @property
    def action_call_graph(self) -> action_call_graph.ActionCallGraph:
        """The actions this program's actions trigger."""
        return self.reference_graph_result.action_call_graph

    @property
    def operation_graphs(
        self,
    ) -> operation_graph.OperationGraphs:
        """Every action's operation dependency graph."""
        return self.reference_graph_result.operation_graphs


class ValidateProject(Protocol):
    """Callable that validates a multi-file project through both phases."""

    def __call__(
        self,
        files: dict[str, str],
        *,
        universe_name: str = ...,
        max_workers: int | None = ...,
        local_deps: dict[str, str] | None = ...,
        sub_roots: dict[str, str] | None = ...,
        entry_file: str = ...,
        allow_entry_action_interface_positions: bool = ...,
    ) -> FullValidationResult:
        """Validate a project with the given files."""
        ...


@pytest.fixture
def validate_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateProject:
    """Set up a multi-file project and run both validation phases."""

    def _run(
        files: dict[str, str],
        *,
        universe_name: str = "my.domain.com:my_lib",
        max_workers: int | None = None,
        local_deps: dict[str, str] | None = None,
        sub_roots: dict[str, str] | None = None,
        # Pass entry_file only when the entry path itself is the behavior under test,
        # such as a test of path mismatches or of a missing entry file. Otherwise
        # do not pass this; leave it as the default.
        entry_file: str = "test.dfn",
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> FullValidationResult:
        test_helpers.write_project_config(tmp_path, universe_name)
        if local_deps is not None:
            test_helpers.write_local_deps_config(tmp_path, local_deps)
            for dep_path in local_deps.values():
                (tmp_path / dep_path).mkdir(parents=True, exist_ok=True)
        if sub_roots is not None:
            for sub_root_path, sub_universe in sub_roots.items():
                test_helpers.write_project_config(
                    tmp_path / sub_root_path, sub_universe
                )
        for name, content in files.items():
            file_path = tmp_path / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        structural_result = program_validator.ProgramStructuralValidator(
            _PARSER,
            allow_entry_action_interface_positions=(
                allow_entry_action_interface_positions
            ),
        ).validate_program(
            PurePosixPath(entry_file),
            max_workers=max_workers,
        )
        return _run_reference_graph_validation(
            structural_result, max_workers=max_workers
        )

    return _run


class ValidateTestdataNonFilesystemWithReferenceGraph(Protocol):
    """Validate the convention-derived non-filesystem source."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        allow_entry_action_interface_positions: bool = ...,
    ) -> validation_result.ProgramValidationResult:
        """Run structural and reference graph validation."""
        ...


class ValidateTestdataStructuralNonFilesystem(Protocol):
    """Validate the convention-derived non-filesystem source structurally."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        allow_entry_action_interface_positions: bool = ...,
    ) -> validation_result.ProgramValidationResult:
        """Run structural validation."""
        ...


class ValidateTestdataStructural(Protocol):
    """Validate the convention-derived filesystem project structurally."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        # Pass this only when the entry path itself is the behavior under test,
        # such as a test of path mismatches or of a missing entry file. Every
        # other test lets test.dfn define /test.
        entry_file: str = ...,
        allow_entry_action_interface_positions: bool = ...,
    ) -> validation_result.ProgramValidationResult:
        """Run structural validation."""
        ...


def _testdata_directory(request: pytest.FixtureRequest) -> Path:
    test_function = cast("pytest.Function", request.node)
    test_class = test_function.parent
    test_class_name = test_class.name if isinstance(test_class, pytest.Class) else None
    return path_resolver.directory_for(
        request.path,
        test_function.name,
        test_class_name,
    )


@pytest.fixture
def testdata_project_directory(
    request: pytest.FixtureRequest,
) -> Path:
    """Return the current test's convention-derived project directory."""
    return _testdata_directory(request)


@pytest.fixture
def validate_testdata_structural_non_filesystem(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataStructuralNonFilesystem:
    """Structurally validate source.dfn from the derived testdata directory."""
    directory = _testdata_directory(request)
    source = (directory / "source.dfn").read_text(encoding="utf-8")

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        return program_validator.ProgramStructuralValidator(
            _PARSER,
            allow_entry_action_interface_positions=(
                allow_entry_action_interface_positions
            ),
        ).validate_program_non_filesystem(source, max_workers=max_workers)

    return _run


@pytest.fixture
def validate_testdata_structural(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataStructural:
    """Validate the current test's convention-derived filesystem project."""
    directory = _testdata_directory(request)

    def _run(
        *,
        max_workers: int | None = None,
        entry_file: str = "test.dfn",
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        return program_validator.ProgramStructuralValidator(
            _PARSER,
            allow_entry_action_interface_positions=(
                allow_entry_action_interface_positions
            ),
        ).validate_program(PurePosixPath(entry_file), max_workers=max_workers)

    return _run


@pytest.fixture
def validate_testdata_non_filesystem_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataNonFilesystemWithReferenceGraph:
    """Validate source.dfn from the current test's derived testdata directory."""
    directory = _testdata_directory(request)
    source = (directory / "source.dfn").read_text(encoding="utf-8")

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        result = program_validator.ProgramStructuralValidator(
            _PARSER,
            allow_entry_action_interface_positions=(
                allow_entry_action_interface_positions
            ),
        ).validate_program_non_filesystem(source, max_workers=max_workers)
        reference_graph_validator.ReferenceGraphValidator(
            result.reference_graph,
            result.definition_results,
        ).validate(max_workers=max_workers)
        return result

    return _run


def _run_reference_graph_validation(
    structural_result: validation_result.ProgramValidationResult,
    *,
    max_workers: int | None = None,
) -> FullValidationResult:
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        structural_result.reference_graph,
        structural_result.definition_results,
    ).validate(max_workers=max_workers)
    return FullValidationResult(
        program_result=structural_result,
        reference_graph_result=reference_graph_result,
    )


class ValidateTestdataProjectWithReferenceGraph(Protocol):
    """Validate the convention-derived filesystem project."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        allow_entry_action_interface_positions: bool = ...,
    ) -> FullValidationResult:
        """Run structural and reference graph validation."""
        ...


@pytest.fixture
def validate_testdata_project_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataProjectWithReferenceGraph:
    """Validate the current test's convention-derived project."""
    directory = _testdata_directory(request)

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> FullValidationResult:
        monkeypatch.chdir(directory)
        structural_result = program_validator.ProgramStructuralValidator(
            _PARSER,
            allow_entry_action_interface_positions=(
                allow_entry_action_interface_positions
            ),
        ).validate_program(PurePosixPath("test.dfn"), max_workers=max_workers)
        return _run_reference_graph_validation(
            structural_result, max_workers=max_workers
        )

    return _run
