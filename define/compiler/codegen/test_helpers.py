"""Shared assertions for code generation tests."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _all_files(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): path.read_text()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def assert_generated_directory_matches(
    expected: Path,
    generated: Path,
):
    """Assert that generated contains exactly the files and contents in expected."""
    expected_files = _all_files(expected)
    generated_files = _all_files(generated)
    _assert_file_contents_match(expected_files, generated_files, expected.name)


def assert_generated_files_match(expected: Path, generated: Path, files: set[Path]):
    """Assert that the selected generated files match their expected contents."""
    expected_files = {str(path): (expected / path).read_text() for path in files}
    generated_files = {str(path): (generated / path).read_text() for path in files}
    _assert_file_contents_match(expected_files, generated_files, expected.name)


def _assert_file_contents_match(
    expected_files: dict[str, str],
    generated_files: dict[str, str],
    expected_name: str,
):
    if expected_files == generated_files:
        return
    differences: list[str] = []
    for relative_path in sorted(set(expected_files) | set(generated_files)):
        expected_content = expected_files.get(relative_path, "")
        generated_content = generated_files.get(relative_path, "")
        if expected_content == generated_content:
            continue
        differences.extend(
            difflib.unified_diff(
                expected_content.splitlines(keepends=True),
                generated_content.splitlines(keepends=True),
                fromfile=f"{expected_name}/{relative_path}",
                tofile=f"generated/{relative_path}",
            )
        )
    pytest.fail("".join(differences))
