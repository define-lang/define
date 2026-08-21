# pyright: reportUnusedCallResult=false
"""Integration tests that generated callees are independent of their callers."""

import difflib
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/reference_graph")
_ADDITIONAL_CALLER_ROOT = Path(
    "define/compiler/codegen/testdata/callee_codegen_independence"
)
_TEST_MODULE = Path("local/my_domain_com/my_lib/test/__init__.py")
_ADDITIONAL_CALLER_MODULE = Path(
    "local/my_domain_com/my_lib/additional_caller/__init__.py"
)
_ADDITIONAL_CALLER_NAME = "additional_caller"
_CALLEE_MODULE = Path("local/my_domain_com/my_lib/callee/__init__.py")
_ADDITIONAL_CALLER_ENTRY_SOURCE = """    } and it does {
        define the position<additional_caller_call> {
            it may only contain particles where {
                it has the action</additional_caller>.
            }
        }
        create a particle in position<additional_caller_call>.
"""


@dataclass(frozen=True, slots=True)
class _Case:
    name: str
    baseline: Path
    callee_module: Path


_CASES = (
    _Case(
        "known_and_unknown_siblings",
        _TESTDATA_ROOT
        / "operation_graph_two_actions_integration"
        / "callee_known_child_and_caller_unknown_sibling_are_disjoint",
        Path("local/my_domain_com/my_lib/destroyer/__init__.py"),
    ),
    _Case(
        "local_cascade",
        _TESTDATA_ROOT
        / "operation_graph_two_actions_integration"
        / "local_cascade_uses_caller_fragment_for_occupied_child",
        Path("local/my_domain_com/my_lib/triggered/__init__.py"),
    ),
    _Case(
        "transitive_disjoint",
        _TESTDATA_ROOT
        / "operation_graph_many_actions_integration"
        / "destruction_cascade_includes_disjoint_child_paths_from_two_callers",
        Path("local/my_domain_com/my_lib/destroyer/__init__.py"),
    ),
)


def _add_additional_caller(source: str) -> str:
    return source.replace(
        "    } and it does {\n",
        _ADDITIONAL_CALLER_ENTRY_SOURCE,
        1,
    )


def _assert_only_additional_caller_was_added(expected: str, actual: str):
    expected_lines = [line for line in expected.splitlines() if line]
    actual_lines = [line for line in actual.splitlines() if line]
    matcher = difflib.SequenceMatcher(a=expected_lines, b=actual_lines)
    for (
        tag,
        _expected_start,
        _expected_end,
        actual_start,
        actual_end,
    ) in matcher.get_opcodes():
        if tag == "equal":
            continue
        added_lines = actual_lines[actual_start:actual_end]
        if tag == "insert" and any(  # pragma: no branch
            _ADDITIONAL_CALLER_NAME in line for line in added_lines
        ):
            continue
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="checked-in expected test module",
            tofile="test module with an additional caller",
        )
        pytest.fail("".join(diff))


def _compile_project(
    project: Path,
    generated: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(project)
    result = driver.Driver().compile_program(Path("test.dfn"), generated)
    assert_no_errors(result)


def _assert_generated_program_runs(generated: Path):
    runtime_result = generated_program_runner.run_generated_program(generated)
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)


def _generate_with_additional_caller(
    source_project: Path,
    additional_caller_source: Path,
    project: Path,
    generated: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    shutil.copytree(source_project, project)
    test_source = project / "test.dfn"
    _ = test_source.write_text(_add_additional_caller(test_source.read_text()))
    shutil.copyfile(additional_caller_source, project / "additional_caller.dfn")
    _compile_project(project, generated, monkeypatch)
    _assert_generated_program_runs(generated)


@pytest.mark.parametrize("case", _CASES, ids=[case.name for case in _CASES])
def test_adding_a_caller_does_not_change_generated_callees(
    case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    baseline_expected = (case.baseline / "expected").resolve()
    additional_caller_source = (
        _ADDITIONAL_CALLER_ROOT / case.name / "additional_caller.dfn"
    ).resolve()
    project = tmp_path / "project"
    generated = tmp_path / "generated"
    _generate_with_additional_caller(
        case.baseline,
        additional_caller_source,
        project,
        generated,
        monkeypatch,
    )

    expected_files = {
        path.relative_to(baseline_expected)
        for path in baseline_expected.rglob("*")
        if path.is_file()
    }
    actual_files = {
        path.relative_to(generated) for path in generated.rglob("*") if path.is_file()
    }
    assert actual_files == expected_files | {_ADDITIONAL_CALLER_MODULE}
    assert (generated / case.callee_module).read_text() == (
        baseline_expected / case.callee_module
    ).read_text()
    for generated_file in expected_files - {_TEST_MODULE}:
        assert (generated / generated_file).read_text() == (
            baseline_expected / generated_file
        ).read_text()
    _assert_only_additional_caller_was_added(
        (baseline_expected / _TEST_MODULE).read_text(),
        (generated / _TEST_MODULE).read_text(),
    )


def test_adding_a_destructor_contributing_caller_does_not_change_generated_callee(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    case_root = (
        _TESTDATA_ROOT
        / "operation_graph_destructor_integration"
        / "caller_added_destructor_fires_in_callee"
    ).resolve()
    caller_sources = (_ADDITIONAL_CALLER_ROOT / "destructor_contribution").resolve()
    baseline_project = tmp_path / "baseline_project"
    shutil.copytree(case_root, baseline_project)
    shutil.copyfile(caller_sources / "baseline_test.dfn", baseline_project / "test.dfn")
    baseline_generated = tmp_path / "baseline_generated"
    _compile_project(baseline_project, baseline_generated, monkeypatch)
    _assert_generated_program_runs(baseline_generated)

    project_with_contributing_caller = tmp_path / "project_with_contributing_caller"
    generated_with_contributing_caller = tmp_path / "generated_with_contributing_caller"
    _generate_with_additional_caller(
        baseline_project,
        caller_sources / "additional_caller.dfn",
        project_with_contributing_caller,
        generated_with_contributing_caller,
        monkeypatch,
    )

    assert (baseline_generated / _CALLEE_MODULE).read_text() == (
        generated_with_contributing_caller / _CALLEE_MODULE
    ).read_text()
    _assert_only_additional_caller_was_added(
        (baseline_generated / _TEST_MODULE).read_text(),
        (generated_with_contributing_caller / _TEST_MODULE).read_text(),
    )
