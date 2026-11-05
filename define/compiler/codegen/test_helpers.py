"""Shared discovery and assertions for code generation tests."""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from define.compiler.codegen import testdata_cases

_CODEGEN_TESTDATA_ROOT = Path("define/testdata/codegen")

# The definition order of unreferenced definitions depends on which worker
# finishes validating them first. In these cases, that order decides the order
# of functions in a shared module or which colliding authority gets a suffix.
_CASES_WITH_NONDETERMINISTIC_DEFINITION_ORDER = frozenset(
    {
        "cross_fqun_walking/unreferenced_authority_conflict",
        "language_names/package_name_avoids_every_function_name",
    }
)


def _all_files(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): path.read_text(encoding="utf-8")
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
    expected_files = {
        str(path): (expected / path).read_text(encoding="utf-8") for path in files
    }
    generated_files = {
        str(path): (generated / path).read_text(encoding="utf-8") for path in files
    }
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


def codegen_test_cases() -> list[Path]:
    """Discover the codegen cases in the test's data."""
    # Each Bazel test target's data holds only its own category of cases.
    return testdata_cases.case_directories(_CODEGEN_TESTDATA_ROOT)


def codegen_test_case_id(test_case_dir: Path) -> str:
    """Identify a case by its category and name."""
    return test_case_dir.relative_to(_CODEGEN_TESTDATA_ROOT).as_posix()


def mark_nondeterministic_definition_order(
    request: pytest.FixtureRequest, test_case_dir: Path
):
    """Expect a mismatch, sometimes, for a case whose generated code depends on definition order."""
    if (
        codegen_test_case_id(test_case_dir)
        in _CASES_WITH_NONDETERMINISTIC_DEFINITION_ORDER
    ):
        request.applymarker(
            pytest.mark.xfail(
                strict=False,
                reason="The definition order of unreferenced definitions is nondeterministic.",
            )
        )
