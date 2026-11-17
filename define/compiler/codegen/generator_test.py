# pyright: reportUnusedCallResult=false

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen import generator, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler import ast
    from define.compiler.association_resolution import concrete_program
    from define.compiler.conftest import ValidateTestdataProjectWithReferenceGraph


def _generate(
    program: concrete_program.ConcreteProgram,
    entry_action: ast.ActionDefinition,
    tmp_path: Path,
    *,
    max_workers: int,
):
    generator.CodeGenerator().generate(
        program, entry_action, tmp_path, max_workers=max_workers
    )


def test_parallel_generation_matches_single_worker(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    tmp_path: Path,
):
    result = validate_testdata_project_with_reference_graph()

    assert_no_errors(result.program_validation)
    program = result.concrete_program
    entry_action = result.program_validation.entry_action
    assert entry_action is not None
    single_worker_dir = tmp_path / "single_worker"
    parallel_dir = tmp_path / "parallel"
    # One worker can complete the diamond only when workers never wait for
    # referenced definitions themselves.
    _generate(program, entry_action, single_worker_dir, max_workers=1)
    _generate(program, entry_action, parallel_dir, max_workers=4)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
    _generate(program, entry_action, single_worker_dir, max_workers=1)
    test_helpers.assert_generated_directory_matches(single_worker_dir, parallel_dir)
