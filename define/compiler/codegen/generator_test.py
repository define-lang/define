# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen import generator, test_helpers
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )
    from define.compiler.validator import validation_result


def _generate(
    program_result: validation_result.ProgramValidationResult,
    tmp_path: Path,
    *,
    max_workers: int | None = None,
):
    entry_action = program_result.entry_action
    assert entry_action is not None
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        program_result.reference_graph,
        program_result.definition_results,
        entry_action=entry_action,
    ).validate()
    assert_no_errors(program_result)
    generator.CodeGenerator().generate(
        reference_graph_result.definition_order,
        reference_graph_result.operation_graphs,
        entry_action,
        tmp_path,
        max_workers=max_workers,
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


def test_parallel_generation_matches_single_worker(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    single_worker_dir = tmp_path / "single_worker"
    parallel_dir = tmp_path / "parallel"
    # One worker can complete the diamond only when workers never wait for
    # referenced definitions themselves.
    _generate(program_result, single_worker_dir, max_workers=1)
    _generate(program_result, parallel_dir, max_workers=4)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
