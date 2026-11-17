# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false
"""Test fixtures that run a program through the whole validation pipeline."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler import validation_pipeline
from define.compiler.test_fixtures import testdata
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler.validator import validation_result


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
        allow_entry_action_occupied_implied_position_requirements: bool = ...,
    ) -> validation_pipeline.CompilerValidationResult:
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
        # Pass True only when a validation test specifically requires an entry
        # action with an occupied implied-position requirement.
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ) -> validation_pipeline.CompilerValidationResult:
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
            file_path.write_text(content, encoding="utf-8", newline="\n")
        monkeypatch.chdir(tmp_path)
        structural_result = program_validator.validate_program(
            PurePosixPath(entry_file),
            max_workers=max_workers,
            allow_entry_action_interface_positions=allow_entry_action_interface_positions,
        )
        return validation_pipeline.validate_and_resolve_program(
            structural_result,
            max_workers=max_workers,
            allow_entry_action_occupied_implied_position_requirements=(
                allow_entry_action_occupied_implied_position_requirements
            ),
        )

    return _run


class ValidateTestdataNonFilesystemWithReferenceGraph(Protocol):
    """Validate the convention-derived non-filesystem source."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        allow_entry_action_interface_positions: bool = ...,
        allow_entry_action_occupied_implied_position_requirements: bool = ...,
    ) -> validation_result.ProgramValidationResult:
        """Run structural and reference graph validation."""
        ...


@pytest.fixture
def validate_testdata_non_filesystem_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataNonFilesystemWithReferenceGraph:
    """Validate source.dfn from the current test's derived testdata directory."""
    directory = testdata.testdata_directory(request)
    source = (directory / "source.dfn").read_text(encoding="utf-8")

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
        # Pass True only when a validation test specifically requires an entry
        # action with an occupied implied-position requirement.
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        return validation_pipeline.validate_and_resolve_program(
            program_validator.validate_program_non_filesystem(
                source,
                max_workers=max_workers,
                allow_entry_action_interface_positions=allow_entry_action_interface_positions,
            ),
            max_workers=max_workers,
            allow_entry_action_occupied_implied_position_requirements=(
                allow_entry_action_occupied_implied_position_requirements
            ),
        ).program_validation

    return _run


class ValidateTestdataProjectWithReferenceGraph(Protocol):
    """Validate the convention-derived filesystem project."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        allow_entry_action_interface_positions: bool = ...,
        allow_entry_action_occupied_implied_position_requirements: bool = ...,
    ) -> validation_pipeline.CompilerValidationResult:
        """Run structural and reference graph validation."""
        ...


@pytest.fixture
def validate_testdata_project_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataProjectWithReferenceGraph:
    """Validate the current test's convention-derived project."""
    directory = testdata.testdata_directory(request)

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
        # Pass True only when a validation test specifically requires an entry
        # action with an occupied implied-position requirement.
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ) -> validation_pipeline.CompilerValidationResult:
        monkeypatch.chdir(directory)
        structural_result = program_validator.validate_program(
            PurePosixPath("test.dfn"),
            max_workers=max_workers,
            allow_entry_action_interface_positions=allow_entry_action_interface_positions,
        )
        return validation_pipeline.validate_and_resolve_program(
            structural_result,
            max_workers=max_workers,
            allow_entry_action_occupied_implied_position_requirements=(
                allow_entry_action_occupied_implied_position_requirements
            ),
        )

    return _run
