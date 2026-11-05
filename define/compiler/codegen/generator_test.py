# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen import generator, test_helpers
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler.conftest import ValidateTestdataStructural
    from define.compiler.validator import validation_result


def _generate(
    program_result: validation_result.ProgramValidationResult,
    tmp_path: Path,
    *,
    max_workers: int,
):
    entry_action = program_result.entry_action
    assert entry_action is not None
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        program_result.definition_order,
        program_result.definition_results,
        entry_action=entry_action,
    ).validate()
    assert_no_errors(program_result)
    generator.CodeGenerator().generate(
        reference_graph_result.codegen_input,
        entry_action,
        tmp_path,
        max_workers=max_workers,
    )


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
