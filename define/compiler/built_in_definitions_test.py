from __future__ import annotations

from pathlib import Path

from define.compiler import ast, built_in_definitions, constants, diagnostics, parser
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator


def test_rational_add_operation():
    operation = built_in_definitions.get_operation(constants.RATIONAL_ADD_OPERATION)
    assert isinstance(operation, ast.ValueOperationDefinition)
    assert operation.typed_name.full_typed_name == constants.RATIONAL_ADD_OPERATION


def test_decimal_ascii_infix_add_encoding_operation():
    operation = built_in_definitions.get_operation(
        constants.DECIMAL_ASCII_INFIX_ADD_ENCODING_OPERATION
    )
    assert isinstance(operation, ast.EncodingOperationDefinition)
    assert (
        operation.typed_name.full_typed_name
        == constants.DECIMAL_ASCII_INFIX_ADD_ENCODING_OPERATION
    )


def test_unknown_operation():
    assert (
        built_in_definitions.get_operation("operation<standard:/number/rational/pow>")
        is None
    )


def test_built_in_source_is_valid_outside_the_standard_universe():
    source = (Path(__file__).parent / "built_in_definitions.dfn").read_text(
        encoding="utf-8"
    )
    result = program_validator.ProgramStructuralValidator(
        parser.Parser()
    ).validate_program_non_filesystem(source)
    _ = reference_graph_validator.ReferenceGraphValidator(
        result.definition_order,
        result.definition_results,
        entry_action=result.entry_action,
    ).validate()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first = result.all_diagnostics[0]
    assert isinstance(first, diagnostics.ReservedUniverseNameDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 3
    assert first.location.column == 22
    assert first.reserved_name == "standard"
    second = result.all_diagnostics[1]
    assert isinstance(second, diagnostics.ReservedUniverseNameDiagnostic)
    assert second.location.file_path is None
    assert second.location.line == 28
    assert second.location.column == 31
    assert second.reserved_name == "standard"
