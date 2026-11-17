# pyright: reportUnusedCallResult=false
"""Test fixtures that validate a testdata program structurally."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler.test_fixtures import testdata
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from define.compiler.validator import validation_result


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


@pytest.fixture
def validate_testdata_structural_non_filesystem(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataStructuralNonFilesystem:
    """Structurally validate source.dfn from the derived testdata directory."""
    directory = testdata.testdata_directory(request)
    source = (directory / "source.dfn").read_text(encoding="utf-8")

    def _run(
        *,
        max_workers: int | None = None,
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        return program_validator.validate_program_non_filesystem(
            source,
            max_workers=max_workers,
            allow_entry_action_interface_positions=allow_entry_action_interface_positions,
        ).result

    return _run


@pytest.fixture
def validate_testdata_structural(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataStructural:
    """Validate the current test's convention-derived filesystem project."""
    directory = testdata.testdata_directory(request)

    def _run(
        *,
        max_workers: int | None = None,
        entry_file: str = "test.dfn",
        # Pass True only when a validation test specifically requires an entry
        # action with interface positions.
        allow_entry_action_interface_positions: bool = False,
    ) -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        return program_validator.validate_program(
            PurePosixPath(entry_file),
            max_workers=max_workers,
            allow_entry_action_interface_positions=allow_entry_action_interface_positions,
        ).result

    return _run
