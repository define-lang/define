# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen import generator, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler.conftest import (
        FullValidationResult,
        ValidateTestdataProjectWithReferenceGraph,
    )


def _generate(
    result: FullValidationResult,
    tmp_path: Path,
    *,
    max_workers: int,
):
    entry_action = result.program_result.entry_action
    assert entry_action is not None
    generator.CodeGenerator().generate(
        result.reference_graph_result.concrete_program,
        entry_action,
        tmp_path,
        max_workers=max_workers,
    )


def test_parallel_generation_matches_single_worker(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    tmp_path: Path,
):
    result = validate_testdata_project_with_reference_graph()

    assert_no_errors(result.program_result)
    single_worker_dir = tmp_path / "single_worker"
    parallel_dir = tmp_path / "parallel"
    # One worker can complete the diamond only when workers never wait for
    # referenced definitions themselves.
    _generate(result, single_worker_dir, max_workers=1)
    _generate(result, parallel_dir, max_workers=4)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
    _generate(result, single_worker_dir, max_workers=1)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
