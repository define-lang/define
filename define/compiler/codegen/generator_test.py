# pyright: reportUnusedCallResult=false

from pathlib import Path

import pytest

from define.compiler.codegen import generated_program_runner, generator
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.test_helpers import assert_no_errors

_DESTRUCTOR_ORDERING_NOT_REPRESENTED = (
    "Destructor ordering is not represented in the operation graph, so cascade "
    "children are destroyed before the parent destructor uses them."
)


def _generate(
    program_result: validation_result.ProgramValidationResult,
    tmp_path: Path,
):
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        program_result.reference_graph,
        program_result.definition_results,
    ).validate()
    entry_action = program_result.entry_action
    assert entry_action is not None
    generator.CodeGenerator().generate(
        program_result.reference_graph,
        reference_graph_result.operation_graphs,
        entry_action,
        tmp_path,
    )


def test_constructor_entry_point_adds_no_diagnostics(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)


def test_file_with_position_and_constructor_passes(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    main_file = tmp_path / "__main__.py"
    assert main_file.exists()
    assert main_file.stat().st_size > 0


def test_constructor_chosen_when_position_constrains_it(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    main_file = tmp_path / "__main__.py"
    assert main_file.exists()
    assert main_file.stat().st_size > 0


@pytest.mark.xfail(strict=True, reason=_DESTRUCTOR_ORDERING_NOT_REPRESENTED)
def test_destructor_fragments_finish_before_cascade_frees_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    completed = generated_program_runner.run_generated_program(
        tmp_path,
        max_threads=1,
    )

    assert (completed.returncode, completed.stderr) == (0, "")


@pytest.mark.xfail(strict=True, reason=_DESTRUCTOR_ORDERING_NOT_REPRESENTED)
def test_destructor_and_known_children_with_caller_known_occupancy(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    completed = generated_program_runner.run_generated_program(
        tmp_path,
        max_threads=1,
    )

    assert (completed.returncode, completed.stderr) == (0, "")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Child position existence known only two callers above is not propagated "
        "to the destroyer's destruction cascade."
    ),
)
def test_destructor_with_children_known_only_two_callers_up(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    destroyer = (
        tmp_path / "local" / "my_domain_com" / "my_lib" / "destroyer" / "__init__.py"
    )

    assert "global_position_extra" in destroyer.read_text()
    completed = generated_program_runner.run_generated_program(
        tmp_path,
        max_threads=1,
    )

    assert (completed.returncode, completed.stderr) == (0, "")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A destructor known only two callers above is not propagated to the "
        "destroyer, so its child positions are destroyed before it executes."
    ),
)
def test_destructor_known_only_two_callers_up(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)
    completed = generated_program_runner.run_generated_program(
        tmp_path,
        max_threads=1,
    )

    assert (completed.returncode, completed.stderr) == (0, "")
