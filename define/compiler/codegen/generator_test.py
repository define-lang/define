# pyright: reportUnusedCallResult=false

from pathlib import Path

from define.compiler.codegen import generator
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.test_helpers import assert_no_errors


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
