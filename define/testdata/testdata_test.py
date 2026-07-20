"""Ensure every convention-organized testdata directory has a Python test owner.

This prevents renaming or removing a test from leaving unused testdata behind.
"""

import ast
import functools
from pathlib import Path

from define.testdata import path_resolver

_TESTDATA_ROOT = Path("define/testdata")
_TEST_SOURCE_ROOTS = {
    "codegen": Path("define/compiler/codegen"),
    "driver": Path("define/compiler"),
    "structural": Path("define/compiler/validator/structural/program_validator_tests"),
    "reference_graph": Path(
        "define/compiler/validator/reference_graph/reference_graph_validator_tests"
    ),
}
_NON_FILESYSTEM_FIXTURES = {
    "validate_testdata_structural_non_filesystem",
    "validate_testdata_non_filesystem_with_reference_graph",
}
_FILESYSTEM_FIXTURES = {
    "validate_testdata_structural",
    "validate_testdata_project_with_reference_graph",
    "testdata_project_directory",
}
_TESTDATA_FIXTURES = _NON_FILESYSTEM_FIXTURES | _FILESYSTEM_FIXTURES
# TODO: Remove this exemption when the temporary generator_integration module is removed.
_BULK_OWNED_MODULES = {Path("codegen/generator_integration")}

# TODO: Require data-backed tests that assert diagnostics to also assert that
# validation produced no exceptions.


def _fixture_arguments(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    argument_names = {argument.arg for argument in function.args.args}
    return argument_names & _TESTDATA_FIXTURES


@functools.cache
def _test_functions(
    test_file: Path,
) -> tuple[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef], ...]:
    tree = ast.parse(test_file.read_text(encoding="utf-8"))
    functions: list[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((None, node))
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append((node.name, member))
    return tuple(functions)


def _scenario_directories() -> list[Path]:
    directories: list[Path] = []
    for phase in _TEST_SOURCE_ROOTS:
        phase_root = _TESTDATA_ROOT / phase
        if not phase_root.exists():
            continue
        for module_directory in phase_root.iterdir():
            relative_module = module_directory.relative_to(_TESTDATA_ROOT)
            if relative_module in _BULK_OWNED_MODULES:
                continue
            if not module_directory.is_dir():
                raise AssertionError(
                    f"unexpected file in {phase_root}: {module_directory}"
                )
            build_file = module_directory / "BUILD.bazel"
            if not build_file.is_file():
                raise AssertionError(f"missing module BUILD file: {build_file}")
            for scenario_directory in module_directory.iterdir():
                if scenario_directory == build_file:
                    continue
                if not scenario_directory.is_dir():
                    raise AssertionError(
                        f"unexpected file in {module_directory}: {scenario_directory}"
                    )
                directories.append(scenario_directory.relative_to(_TESTDATA_ROOT))
    return sorted(directories)


def _layout_for(relative_directory: Path) -> str:
    phase, module_name, case_name = relative_directory.parts
    test_file = _TEST_SOURCE_ROOTS[phase] / f"{module_name}_test.py"
    assert test_file.is_file(), (
        f"testdata directory has no test module: {relative_directory}"
    )
    matching_owners = [
        (class_name, function)
        for class_name, function in _test_functions(test_file)
        if function.name.startswith("test_")
        and path_resolver.case_name_for(function.name, class_name) == case_name
    ]
    assert len(matching_owners) == 1, (
        f"testdata directory must have exactly one owner in {test_file}: "
        + f"{relative_directory}, found {len(matching_owners)}"
    )
    _, function = matching_owners[0]
    fixtures = _fixture_arguments(function)
    assert len(fixtures) == 1, (
        f"{test_file}:{function.lineno} must use exactly one testdata fixture, "
        + f"found {sorted(fixtures)}"
    )
    fixture = fixtures.pop()
    return "non_filesystem" if fixture in _NON_FILESYSTEM_FIXTURES else "filesystem"


def test_testdata_directories_have_consumers():
    for relative_directory in _scenario_directories():
        layout = _layout_for(relative_directory)
        source_path = _TESTDATA_ROOT / relative_directory / "source.dfn"
        if layout == "non_filesystem":
            assert source_path.is_file(), (
                f"missing non-filesystem source: {source_path}"
            )
        else:
            assert not source_path.exists(), (
                f"filesystem testdata cannot contain source.dfn: {source_path}"
            )
