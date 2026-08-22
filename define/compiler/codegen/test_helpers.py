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
                fromfile=f"{expected.name}/{relative_path}",
                tofile=f"generated/{relative_path}",
            )
        )
    pytest.fail("".join(differences))
