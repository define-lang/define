from __future__ import annotations

from pathlib import Path

from define.compiler import ast, built_in_definitions, constants
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics
from define.compiler.graphs import reference_graph, reference_graph_order
from define.compiler.parsing import parser
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import file_validator, program_validator


def test_decimal_ascii_encoding():
    definition = built_in_definitions.get_definition(constants.DECIMAL_ASCII_ENCODING)
    assert isinstance(definition, ast.EncodingDefinition)


def test_number_potential_literal():
    definition = built_in_definitions.get_definition("literal<standard:/number>")
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert definition.encoding.full_typed_name == constants.DECIMAL_ASCII_ENCODING


def test_rational_value():
    definition = built_in_definitions.get_definition("value<standard:/number/rational>")
    assert isinstance(definition, ast.ValueDefinition)


def test_rational_add_operation():
    definition = built_in_definitions.get_definition(
        "operation<standard:/number/rational/add>"
    )
    assert isinstance(definition, ast.ValueOperationDefinition)


def test_decimal_ascii_infix_add_encoding_operation():
    definition = built_in_definitions.get_definition(
        "encoding_operation<standard:/number/decimal/ascii/infix_add>"
    )
    assert isinstance(definition, ast.EncodingOperationDefinition)


def test_unknown_definition():
    assert (
        built_in_definitions.get_definition("operation<standard:/number/rational/pow>")
        is None
    )


def test_every_definition():
    names = [
        definition.typed_name.full_typed_name
        for definition in built_in_definitions.definitions()
    ]
    assert names == [
        "encoding<standard:/number/decimal/ascii>",
        "literal<standard:/number>",
        "value<standard:/number/rational>",
        "operation<standard:/number/rational/add>",
        "encoding_operation<standard:/number/decimal/ascii/infix_add>",
    ]


def _built_in_source() -> str:
    return (Path(__file__).parent / "built_in_definitions.dfn").read_text(
        encoding="utf-8"
    )


def test_built_in_source_is_valid_outside_the_standard_universe():
    source = _built_in_source()
    result = program_validator.ProgramStructuralValidator(
        parser.Parser()
    ).validate_program_non_filesystem(source)
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 5
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ReservedUniverseNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 21
    assert diagnostic.reserved_name == "standard"
    diagnostic = result.all_diagnostics[1]
    assert isinstance(diagnostic, diagnostics.ReservedUniverseNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 5
    assert diagnostic.location.column == 30
    assert diagnostic.reserved_name == "standard"
    diagnostic = result.all_diagnostics[2]
    assert isinstance(diagnostic, diagnostics.ReservedUniverseNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 9
    assert diagnostic.location.column == 28
    assert diagnostic.reserved_name == "standard"
    diagnostic = result.all_diagnostics[3]
    assert isinstance(diagnostic, diagnostics.ReservedUniverseNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 11
    assert diagnostic.location.column == 22
    assert diagnostic.reserved_name == "standard"
    diagnostic = result.all_diagnostics[4]
    assert isinstance(diagnostic, diagnostics.ReservedUniverseNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 36
    assert diagnostic.location.column == 31
    assert diagnostic.reserved_name == "standard"


def test_built_in_definitions_pass_reference_graph_validation():
    # A program resolves references to standard names to the built-in
    # definitions themselves, so this validates them without a program.
    file_result = file_validator.FileStructuralValidator(
        parser.Parser()
    ).validate_source(_built_in_source())
    graph = reference_graph.ReferenceGraph()
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ] = typed_name_dict.TypedNameDict()
    for definition_result in file_result.definition_results:
        definition = definition_result.definition
        graph.add_definition(definition)
        definition_results[definition.typed_name] = (
            validation_result.DefinitionValidationResult(definition=definition)
        )
    for definition_result in file_result.definition_results:
        for edge in definition_result.reference_edges:
            assert graph.try_add_edge(edge) is None
    _ = reference_graph_validator.ReferenceGraphValidator(
        reference_graph_order.ReferenceGraphOrder(graph),
        definition_results,
        entry_action=None,
    ).validate()
    all_diagnostics: list[diagnostics.Diagnostic] = []
    for definition_result in definition_results.values():
        all_diagnostics.extend(definition_result.diagnostics)
    assert all_diagnostics == []
