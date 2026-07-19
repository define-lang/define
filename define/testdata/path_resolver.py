"""Resolve convention-organized Define testdata paths."""

import re
from pathlib import Path

_TESTDATA_ROOT = Path("define/testdata")
_PHASE_BY_TEST_DIRECTORY = {
    "parser_tests": "parser",
    "program_validator_tests": "structural",
    "reference_graph_validator_tests": "reference_graph",
}


def _snake_case(class_name: str) -> str:
    with_word_boundaries = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_word_boundaries).lower()


def case_name_for(test_name: str, test_class_name: str | None = None) -> str:
    """Return the scenario directory name for a Python test."""
    if not test_name.startswith("test_"):
        raise ValueError(f"test function must start with test_: {test_name}")
    case_name = test_name.removeprefix("test_")
    if test_class_name is None:
        return case_name
    if not test_class_name.startswith("Test"):
        raise ValueError(f"test class must start with Test: {test_class_name}")
    class_name = test_class_name.removeprefix("Test")
    if not class_name:
        raise ValueError("test class must have a name after Test")
    return f"{_snake_case(class_name)}__{case_name}"


def directory_for(
    test_file: Path,
    test_name: str,
    test_class_name: str | None = None,
) -> Path:
    """Return the convention-derived testdata directory for a test."""
    test_directories = set(test_file.parts) & _PHASE_BY_TEST_DIRECTORY.keys()
    if len(test_directories) != 1:
        raise ValueError(f"cannot determine testdata phase for {test_file}")
    test_directory = test_directories.pop()
    if not test_file.stem.endswith("_test"):
        raise ValueError(f"test module must end in _test: {test_file}")
    phase = _PHASE_BY_TEST_DIRECTORY[test_directory]
    module_name = test_file.stem.removesuffix("_test")
    case_name = case_name_for(test_name, test_class_name)
    directory = _TESTDATA_ROOT / phase / module_name / case_name
    if not directory.is_dir():
        raise FileNotFoundError(
            f"testdata directory for {test_file.name}::{test_name} not found: "
            + f"{directory}"
        )
    return directory
