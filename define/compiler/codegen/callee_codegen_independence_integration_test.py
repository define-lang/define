# pyright: reportUnusedCallResult=false
"""Integration tests that generated callees are independent of their callers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/reference_graph")
_ADDITIONAL_CALLER_ROOT = Path(
    "define/compiler/codegen/testdata/callee_codegen_independence"
)
_TEST_MODULE = Path("local/my_domain_com/my_lib/test/__init__.py")
_ADDITIONAL_CALLER_MODULE = Path(
    "local/my_domain_com/my_lib/additional_caller/__init__.py"
)
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


@dataclass(frozen=True, slots=True)
class _DestructorContributionCase(_Case):
    callee_module: Path
    caller_sources: Path


_CASES = (
    _Case(
        "known_and_unknown_siblings",
        _TESTDATA_ROOT
        / "operation_graph_two_actions_integration"
        / "callee_known_child_and_caller_unknown_sibling_are_disjoint",
    ),
    _Case(
        "local_cascade",
        _TESTDATA_ROOT
        / "operation_graph_two_actions_integration"
        / "local_cascade_uses_caller_fragment_for_occupied_child",
    ),
    _Case(
        "transitive_disjoint",
        _TESTDATA_ROOT
        / "operation_graph_many_actions_integration"
        / "destruction_cascade_includes_disjoint_child_paths_from_two_callers",
    ),
)

_DESTRUCTOR_CONTRIBUTION_CASES = (
    _DestructorContributionCase(
        name="requirement_free",
        baseline=(
            _TESTDATA_ROOT
            / "operation_graph_destructor_integration"
            / "caller_added_destructor_fires_in_callee"
        ),
        callee_module=Path("local/my_domain_com/my_lib/callee/__init__.py"),
        caller_sources=_ADDITIONAL_CALLER_ROOT / "destructor_contribution",
    ),
    _DestructorContributionCase(
        name="contracted_position_requirements",
        baseline=(
            _TESTDATA_ROOT
            / "operation_graph_destructor_integration"
            / "caller_contributed_child_destructor_depends_on_callee_guarantee"
        ),
        callee_module=Path("local/my_domain_com/my_lib/destroyer/__init__.py"),
        caller_sources=(
            _ADDITIONAL_CALLER_ROOT / "requirementful_destructor_contribution"
        ),
    ),
)


_LATER_INIT_CONFIGURATION_CASES = [
    pytest.param(
        "contributed_destructor_move_removes_fill_after_two_destruction_dependencies",
        "extra_destructor",
        ("test", "caller"),
        marks=pytest.mark.xfail(
            strict=False,
            raises=pytest.fail.Exception,
            reason="S4: concurrent initialization can use a callee execution before it exists",
        ),
    ),
    pytest.param(
        "caller_configures_destructor_after_independent_inits",
        "extra_destructor",
        ("test", "caller"),
        marks=pytest.mark.xfail(
            strict=False,
            raises=pytest.fail.Exception,
            reason="S4: concurrent initialization can use a callee execution before it exists",
        ),
    ),
    pytest.param(
        "caller_configures_multiple_destroys_after_independent_inits",
        "extra_destructor",
        ("test", "caller"),
        marks=pytest.mark.xfail(
            strict=False,
            raises=pytest.fail.Exception,
            reason="S4: concurrent initialization can use a callee execution before it exists",
        ),
    ),
    pytest.param(
        "caller_configures_multiple_destroys_after_separate_binding_inits",
        "extra_destructor",
        ("test",),
    ),
    pytest.param(
        "caller_configures_destructor_after_callee_guarantee_and_local_move",
        "extra_destructor",
        ("test",),
    ),
    pytest.param(
        "caller_configures_destructor_after_callee_initializes_fanout_owner",
        "extra_destructor",
        ("test",),
    ),
    pytest.param(
        "caller_configures_destructor_after_two_separate_binding_inits",
        "extra_destructor",
        ("test",),
    ),
    pytest.param(
        "caller_configures_destructor_after_three_separate_binding_inits",
        "extra_destructor",
        ("test",),
    ),
    pytest.param(
        "later_caller_configures_destructor_after_separate_binding_inits",
        "later_destructor",
        ("test",),
    ),
]


@pytest.mark.parametrize(
    ("case_name", "additional_destructor", "contributing_sources"),
    _LATER_INIT_CONFIGURATION_CASES,
)
def test_later_init_configuration_does_not_change_generated_callees(
    case_name: str,
    additional_destructor: str,
    contributing_sources: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    case = _TESTDATA_ROOT / "operation_graph_destructor_integration" / case_name
    expected = (case / "expected").resolve()
    project = tmp_path / "project"
    generated = tmp_path / "generated"
    shutil.copytree(case, project)
    contributing_modules = _remove_destructor_constraints(
        project, additional_destructor, contributing_sources
    )
    _compile_and_run_project(project, generated, monkeypatch)
    expected_files = _generated_files(expected)
    actual_files = _generated_files(generated)
    additional_destructor_module = Path(
        f"local/my_domain_com/my_lib/{additional_destructor}/__init__.py"
    )
    assert actual_files == expected_files - {additional_destructor_module}
    test_helpers.assert_generated_files_match(
        expected, generated, actual_files - contributing_modules
    )


def _remove_destructor_constraints(
    project: Path,
    additional_destructor: str,
    contributing_sources: tuple[str, ...],
) -> set[Path]:
    contributing_modules: set[Path] = set()
    constraint = f"it has the action</{additional_destructor}>."
    for source_name in contributing_sources:
        source = project / f"{source_name}.dfn"
        source_text = source.read_text()
        assert source_text.count(constraint) == 1
        retained_lines: list[str] = []
        for line in source_text.splitlines(keepends=True):
            if line.strip() != constraint:
                retained_lines.append(line)
        source.write_text("".join(retained_lines))
        contributing_modules.add(
            Path(f"local/my_domain_com/my_lib/{source_name}/__init__.py")
        )
    return contributing_modules


def _generated_files(directory: Path) -> set[Path]:
    return {
        path.relative_to(directory) for path in directory.rglob("*") if path.is_file()
    }


def _add_additional_caller(source: str) -> str:
    return source.replace(
        "    } and it does {\n",
        _ADDITIONAL_CALLER_ENTRY_SOURCE,
        1,
    )


def _compile_and_run_project(
    project: Path,
    generated: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(project)
    result = driver.Driver().compile_program(Path("test.dfn"), generated)
    assert_no_errors(result)
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
    _compile_and_run_project(project, generated, monkeypatch)


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

    expected_files = _generated_files(baseline_expected)
    actual_files = _generated_files(generated)
    assert actual_files == expected_files | {_ADDITIONAL_CALLER_MODULE}
    test_helpers.assert_generated_files_match(
        baseline_expected, generated, expected_files - {_TEST_MODULE}
    )


@pytest.mark.parametrize(
    "case",
    _DESTRUCTOR_CONTRIBUTION_CASES,
    ids=[case.name for case in _DESTRUCTOR_CONTRIBUTION_CASES],
)
def test_adding_a_destructor_contributing_caller_does_not_change_generated_callee(
    case: _DestructorContributionCase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    case_root = case.baseline.resolve()
    caller_sources = case.caller_sources.resolve()
    baseline_project = tmp_path / "baseline_project"
    shutil.copytree(case_root, baseline_project)
    shutil.copyfile(caller_sources / "baseline_test.dfn", baseline_project / "test.dfn")
    baseline_generated = tmp_path / "baseline_generated"
    _compile_and_run_project(baseline_project, baseline_generated, monkeypatch)

    project_with_contributing_caller = tmp_path / "project_with_contributing_caller"
    generated_with_contributing_caller = tmp_path / "generated_with_contributing_caller"
    _generate_with_additional_caller(
        baseline_project,
        caller_sources / "additional_caller.dfn",
        project_with_contributing_caller,
        generated_with_contributing_caller,
        monkeypatch,
    )

    test_helpers.assert_generated_files_match(
        baseline_generated, generated_with_contributing_caller, {case.callee_module}
    )
