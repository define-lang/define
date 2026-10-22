# pyright: reportUnusedCallResult=false
"""Value setting statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        NativeParse,
        NativeParseWithDiagnostics,
    )


def test_action_statements_block_with_value_setting_local_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [source_name] = statement.target_position.typed_names
    assert isinstance(source_name, ast.LocalTypedNameReference)
    assert source_name.name_type == name_types.NameType.POSITION
    assert source_name.name_content.name == "source"
    assert isinstance(statement.source, ast.PositionReference)
    [dest] = statement.source.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=60
    )


def test_action_statements_block_with_value_setting_short_global_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [source_name] = statement.target_position.typed_names
    assert isinstance(source_name, ast.GlobalTypedNameReference)
    assert source_name.name_type == name_types.NameType.POSITION
    assert source_name.name_content.fqun is None
    assert source_name.name_content.path.name == "/source"
    assert isinstance(statement.source, ast.PositionReference)
    [dest] = statement.source.typed_names
    assert isinstance(dest, ast.GlobalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.fqun is None
    assert dest.name_content.path.name == "/dest"
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=62
    )


def test_action_statements_block_with_value_setting_full_global_positions(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<mv:define-lang.org:parser:/source> to position<mv:define-lang.org:parser:/dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [source_name] = statement.target_position.typed_names
    assert isinstance(source_name, ast.GlobalTypedNameReference)
    assert source_name.name_type == name_types.NameType.POSITION
    source_fqun = source_name.name_content.fqun
    assert source_fqun is not None
    assert source_fqun.multiverse is not None
    assert source_fqun.multiverse.name == "mv"
    assert source_fqun.authority is not None
    assert source_fqun.authority.name == "define-lang.org"
    assert source_fqun.universe.name == "parser"
    assert source_name.name_content.path.name == "/source"
    assert isinstance(statement.source, ast.PositionReference)
    [dest] = statement.source.typed_names
    assert isinstance(dest, ast.GlobalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    dest_fqun = dest.name_content.fqun
    assert dest_fqun is not None
    assert dest_fqun.multiverse is not None
    assert dest_fqun.multiverse.name == "mv"
    assert dest_fqun.authority is not None
    assert dest_fqun.authority.name == "define-lang.org"
    assert dest_fqun.universe.name == "parser"
    assert dest.name_content.path.name == "/dest"
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=114
    )


def test_action_statements_block_with_value_setting_chained_target(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src>::action</deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [src, deposit, inner] = statement.target_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(inner, ast.LocalTypedNameReference)
    assert inner.name_type == name_types.NameType.POSITION
    assert inner.name_content.name == "inner"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=26, end_line=6, end_column=73
    )
    assert isinstance(statement.source, ast.PositionReference)
    [dest] = statement.source.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"


def test_action_statements_block_with_value_setting_chained_source(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src> to position<dest>::action</deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [src] = statement.target_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    source = statement.source
    assert isinstance(source, ast.PositionReference)
    [dest, deposit, inner] = source.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(inner, ast.LocalTypedNameReference)
    assert inner.name_type == name_types.NameType.POSITION
    assert inner.name_content.name == "inner"
    assert source.location == ast.SourceLocation(
        line=6, column=43, end_line=6, end_column=91
    )


def test_action_statements_block_with_value_setting_both_chained(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src>::action</a1> to position<dest>::action</a2>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [src, a1] = statement.target_position.typed_names
    assert isinstance(src, ast.LocalTypedNameReference)
    assert src.name_type == name_types.NameType.POSITION
    assert src.name_content.name == "src"
    assert isinstance(a1, ast.GlobalTypedNameReference)
    assert a1.name_type == name_types.NameType.ACTION
    assert a1.name_content.fqun is None
    assert a1.name_content.path.name == "/a1"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=26, end_line=6, end_column=51
    )
    source = statement.source
    assert isinstance(source, ast.PositionReference)
    [dest, a2] = source.typed_names
    assert isinstance(dest, ast.LocalTypedNameReference)
    assert dest.name_type == name_types.NameType.POSITION
    assert dest.name_content.name == "dest"
    assert isinstance(a2, ast.GlobalTypedNameReference)
    assert a2.name_type == name_types.NameType.ACTION
    assert a2.name_content.fqun is None
    assert a2.name_content.path.name == "/a2"
    assert source.location == ast.SourceLocation(
        line=6, column=56, end_line=6, end_column=82
    )


def test_action_statements_block_with_mixed_create_and_move_statements(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "        set the value of position<run> to position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [create_statement, value_setting_statement] = (
        definition.action_statements.statements
    )
    assert isinstance(create_statement, ast.CreateParticleStatement)
    [create_run] = create_statement.target_position.typed_names
    assert isinstance(create_run, ast.LocalTypedNameReference)
    assert create_run.name_type == name_types.NameType.POSITION
    assert create_run.name_content.name == "run"
    assert create_statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=43
    )
    assert isinstance(value_setting_statement, ast.ValueSettingStatement)
    [value_setting_run] = value_setting_statement.target_position.typed_names
    assert isinstance(value_setting_run, ast.LocalTypedNameReference)
    assert value_setting_run.name_type == name_types.NameType.POSITION
    assert value_setting_run.name_content.name == "run"
    assert isinstance(value_setting_statement.source, ast.PositionReference)
    [done] = value_setting_statement.source.typed_names
    assert isinstance(done, ast.LocalTypedNameReference)
    assert done.name_type == name_types.NameType.POSITION
    assert done.name_content.name == "done"
    assert value_setting_statement.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=57
    )


def test_action_statements_block_with_value_setting_mixed_local_and_global(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<local_src> to position</global_dest>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.ValueSettingStatement)
    [local_src] = statement.target_position.typed_names
    assert isinstance(local_src, ast.LocalTypedNameReference)
    assert local_src.name_type == name_types.NameType.POSITION
    assert local_src.name_content.name == "local_src"
    assert isinstance(statement.source, ast.PositionReference)
    [global_dest] = statement.source.typed_names
    assert isinstance(global_dest, ast.GlobalTypedNameReference)
    assert global_dest.name_type == name_types.NameType.POSITION
    assert global_dest.name_content.fqun is None
    assert global_dest.name_content.path.name == "/global_dest"
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=71
    )


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
    + "    it happens when {\n"
    + "        this particle is created.\n"
    + "    } and it does {\n"
)


def test_missing_to(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        native_parse(
            _ACTION_PREFIX + "        set the value of position<dest>.\n" + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 40
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 40


def test_missing_source(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingValueSource) as error:
        native_parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to .\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 44
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 44


def test_missing_target(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingPositionReference) as error:
        native_parse(_ACTION_PREFIX + "        set the value of .\n" + "    }\n}\n")
    assert error.value.location.line == 5
    assert error.value.location.column == 26
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 26


def test_missing_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedChainSeparatorOrTerminator) as error:
        native_parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to position<src>\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 57
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 57


def test_value_setting_outside_action(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        native_parse("set the value of position<dest> to position<src>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 49


def test_missing_to_at_eof(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        native_parse(_ACTION_PREFIX + "        set the value of position<dest>")
    assert error.value.location.line == 5
    assert error.value.location.column == 40
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 40


def test_missing_to_after_chained_target(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        native_parse(
            _ACTION_PREFIX
            + "        set the value of position<dest>::position<child>.\n"
            + "    }\n}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 57
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 57


def test_missing_to_during_transformation(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        _ACTION_PREFIX
        + "        move the particle in position<src> to position<dest>.\n"
        + "        set the value of position<dest>"
    )
    assert result.diagnostics == []
    assert isinstance(
        result.exception, parser_exceptions.InvalidValueSettingStatementSyntax
    )
    assert result.exception.location == ast.SourceLocation(
        line=6, column=40, end_line=6, end_column=40
    )


def test_missing_move_to_after_value_setting(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        _ACTION_PREFIX
        + "        set the value of position<dest> to position<src>.\n"
        + "        move the particle in position<src>.\n"
        + "    }\n}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.location == ast.SourceLocation(
        line=6, column=43, end_line=6, end_column=43
    )


def test_extra_space_after_to_in_value_setting(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        set the value of position<run> to  position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 43


def test_value_setting_ends_after_to(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingValueSource) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        set the value of position<run> to\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 42
