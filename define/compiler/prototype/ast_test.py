import pytest

from define.compiler.prototype import ast

# Program.get_abstract_universe tests


def test_get_abstract_universe_found():
    abstract_universe = ast.UniverseBlock(name="AbstractUniverse", statements=[])
    physical_universe = ast.UniverseBlock(name="PhysicalUniverse", statements=[])
    program = ast.Program(universes=[abstract_universe, physical_universe])
    result = program.get_abstract_universe()
    assert result is abstract_universe


def test_get_abstract_universe_not_found():
    physical_universe = ast.UniverseBlock(name="PhysicalUniverse", statements=[])
    program = ast.Program(universes=[physical_universe])
    with pytest.raises(ast.UniverseNotFoundError) as exc_info:
        program.get_abstract_universe()
    assert "Universe 'AbstractUniverse' not found" in str(exc_info.value)


# Program.get_physical_universe tests


def test_get_physical_universe_found():
    abstract_universe = ast.UniverseBlock(name="AbstractUniverse", statements=[])
    physical_universe = ast.UniverseBlock(name="PhysicalUniverse", statements=[])
    program = ast.Program(universes=[abstract_universe, physical_universe])
    result = program.get_physical_universe()
    assert result is physical_universe


def test_get_physical_universe_not_found():
    abstract_universe = ast.UniverseBlock(name="AbstractUniverse", statements=[])
    program = ast.Program(universes=[abstract_universe])
    with pytest.raises(ast.UniverseNotFoundError) as exc_info:
        program.get_physical_universe()
    assert "Universe 'PhysicalUniverse' not found" in str(exc_info.value)


# UniverseBlock.get_statements_by_type tests


def test_get_statements_by_type_single_match():
    type_decl = ast.TypeDeclaration(type_name="Foo", parent_type="Bar")
    prop_decl = ast.PropertyDeclaration(
        type_name="Foo", property_type="String", property_name="value"
    )
    universe = ast.UniverseBlock(
        name="AbstractUniverse", statements=[type_decl, prop_decl]
    )
    result = universe.get_statements_by_type(ast.TypeDeclaration)
    assert len(result) == 1
    assert result[0] is type_decl


def test_get_statements_by_type_multiple_matches():
    type_decl1 = ast.TypeDeclaration(type_name="Foo", parent_type="Bar")
    type_decl2 = ast.TypeDeclaration(type_name="Baz", parent_type="Qux")
    prop_decl = ast.PropertyDeclaration(
        type_name="Foo", property_type="String", property_name="value"
    )
    universe = ast.UniverseBlock(
        name="AbstractUniverse", statements=[type_decl1, prop_decl, type_decl2]
    )
    result = universe.get_statements_by_type(ast.TypeDeclaration)
    assert len(result) == 2
    assert result[0] is type_decl1
    assert result[1] is type_decl2


def test_get_statements_by_type_no_matches():
    type_decl = ast.TypeDeclaration(type_name="Foo", parent_type="Bar")
    universe = ast.UniverseBlock(name="AbstractUniverse", statements=[type_decl])
    result = universe.get_statements_by_type(ast.PropertyDeclaration)
    assert len(result) == 0


def test_get_statements_by_type_subclass():
    compiler_type = ast.CompilerTypeDeclaration(type_name="Number")
    type_decl = ast.TypeDeclaration(type_name="Foo", parent_type="Bar")
    universe = ast.UniverseBlock(
        name="AbstractUniverse", statements=[compiler_type, type_decl]
    )
    result = universe.get_statements_by_type(ast.BaseTypeDeclaration)
    assert len(result) == 2
    assert result[0] is compiler_type
    assert result[1] is type_decl


# StringLiteral.value tests


def test_string_literal_value_simple():
    literal = ast.StringLiteral(raw_value='"hello"')
    assert literal.value == "hello"


def test_string_literal_value_with_escaped_quote():
    literal = ast.StringLiteral(raw_value='"hello \\"world\\""')
    assert literal.value == 'hello "world"'


def test_string_literal_value_with_escaped_backslash():
    literal = ast.StringLiteral(raw_value='"hello\\\\world"')
    assert literal.value == "hello\\world"


def test_string_literal_value_with_both_escapes():
    literal = ast.StringLiteral(raw_value='"hello\\\\world\\"test"')
    assert literal.value == 'hello\\world"test'


def test_string_literal_value_empty_string():
    literal = ast.StringLiteral(raw_value='""')
    assert literal.value == ""


def test_string_literal_value_no_quotes():
    literal = ast.StringLiteral(raw_value="hello")
    with pytest.raises(ast.StringLiteralError) as exc_info:
        _ = literal.value
    assert "Invalid string literal: 'hello'" in str(exc_info.value)


def test_string_literal_value_only_start_quote():
    literal = ast.StringLiteral(raw_value='"hello')
    with pytest.raises(ast.StringLiteralError) as exc_info:
        _ = literal.value
    assert "Invalid string literal: '\"hello'" in str(exc_info.value)


def test_string_literal_value_only_end_quote():
    literal = ast.StringLiteral(raw_value='hello"')
    with pytest.raises(ast.StringLiteralError) as exc_info:
        _ = literal.value
    assert "Invalid string literal: 'hello\"'" in str(exc_info.value)


# NumberLiteral.value tests


def test_number_literal_value_integer():
    literal = ast.NumberLiteral(raw_value="42")
    assert literal.value == 42
    assert isinstance(literal.value, int)


def test_number_literal_value_float():
    literal = ast.NumberLiteral(raw_value="3.14")
    assert literal.value == 3.14
    assert isinstance(literal.value, float)


def test_number_literal_value_zero():
    literal = ast.NumberLiteral(raw_value="0")
    assert literal.value == 0
    assert isinstance(literal.value, int)


def test_number_literal_value_negative_integer():
    literal = ast.NumberLiteral(raw_value="-42")
    assert literal.value == -42
    assert isinstance(literal.value, int)


def test_number_literal_value_negative_float():
    literal = ast.NumberLiteral(raw_value="-3.14")
    assert literal.value == -3.14
    assert isinstance(literal.value, float)


def test_number_literal_value_float_with_trailing_zero():
    literal = ast.NumberLiteral(raw_value="3.0")
    assert literal.value == 3.0
    assert isinstance(literal.value, float)


def test_number_literal_value_invalid():
    literal = ast.NumberLiteral(raw_value="not_a_number")
    with pytest.raises(ast.NumberLiteralError) as exc_info:
        _ = literal.value
    assert "Invalid number literal: 'not_a_number'" in str(exc_info.value)


def test_number_literal_value_empty():
    literal = ast.NumberLiteral(raw_value="")
    with pytest.raises(ast.NumberLiteralError) as exc_info:
        _ = literal.value
    assert "Invalid number literal: ''" in str(exc_info.value)
