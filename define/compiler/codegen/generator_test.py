# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen import generated_program_runner, generator, test_helpers
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
    trace_operations: bool = False,
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
        reference_graph_result.codegen_input,
        entry_action,
        tmp_path,
        max_workers=max_workers,
        trace_operations=trace_operations,
    )


def test_constructor_entry_point_adds_no_diagnostics(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()

    assert_no_errors(program_result)
    _generate(program_result, tmp_path)


def test_last_constructor_is_the_entry_point(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()
    assert_no_errors(program_result)
    entry_action = program_result.entry_action
    assert entry_action is not None
    assert (
        entry_action.typed_name.full_typed_name == "action<my.domain.com:my_lib:/last>"
    )
    _generate(program_result, tmp_path)
    assert "my_lib.last" in (tmp_path / "__main__.py").read_text()
    runtime_result = generated_program_runner.run_generated_program(tmp_path)
    assert runtime_result.returncode == 0
    assert runtime_result.stdout == ""
    assert runtime_result.stderr == ""


def test_non_filesystem_entry_executes_filesystem_constructor(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
    tmp_path: Path,
):
    program_result = validate_testdata_structural_non_filesystem()
    assert_no_errors(program_result)
    entry_action = program_result.entry_action
    assert entry_action is not None
    assert (
        entry_action.typed_name.full_typed_name == "action<my.domain.com:my_lib:/start>"
    )
    _generate(program_result, tmp_path, trace_operations=True)
    trace_file = tmp_path / "operation_trace.txt"
    runtime_result = generated_program_runner.run_generated_program(
        tmp_path, operation_trace_file=trace_file
    )
    assert runtime_result.returncode == 0
    assert runtime_result.stdout == ""
    assert runtime_result.stderr == ""
    assert trace_file.read_text().splitlines() == [
        "start.create(job)",
        "worker.create(item)",
        "start.destroy(job::/worker::item)",
        "start.destroy(job)",
    ]


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
    _generate(program_result, single_worker_dir, max_workers=1)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
