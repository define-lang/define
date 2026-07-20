# pyright: reportUnusedCallResult=false

from pathlib import Path

from define.compiler import diagnostics
from define.compiler.codegen import generator
from define.compiler.conftest import ValidateTestdataStructural
from define.compiler.validator import validation_result
from define.compiler.validator.test_helpers import assert_no_errors


def _generate(
    program_result: validation_result.ProgramValidationResult,
    tmp_path: Path,
) -> list[diagnostics.Diagnostic]:
    first_file = program_result.file_results[0]
    entry_file_definitions = tuple(r.definition for r in first_file.definition_results)
    return generator.CodeGenerator().generate(
        program_result.reference_graph, entry_file_definitions, tmp_path
    )


def test_constructor_entry_point_adds_no_diagnostics(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    result = _generate(program_result, tmp_path)

    assert result == []


def test_position_entry_point_adds_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    result = _generate(program_result, tmp_path)

    assert len(result) == 1
    assert isinstance(result[0], diagnostics.EntryPointNotConstructorDiagnostic)
    assert result[0].location.line == 1
    assert result[0].location.column == 1


def test_non_constructor_action_entry_point_adds_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    result = _generate(program_result, tmp_path)

    assert len(result) == 1
    assert isinstance(result[0], diagnostics.EntryPointNotConstructorDiagnostic)
    assert result[0].location.line == 1
    assert result[0].location.column == 1


def test_file_with_position_and_constructor_passes(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    assert _generate(program_result, tmp_path) == []
    main_file = tmp_path / "__main__.py"
    assert main_file.exists()
    assert main_file.stat().st_size > 0


def test_constructor_chosen_when_position_constrains_it(
    validate_testdata_structural: ValidateTestdataStructural,
    tmp_path: Path,
):
    program_result = validate_testdata_structural()

    assert_no_errors(program_result)
    assert _generate(program_result, tmp_path) == []
    main_file = tmp_path / "__main__.py"
    assert main_file.exists()
    assert main_file.stat().st_size > 0
