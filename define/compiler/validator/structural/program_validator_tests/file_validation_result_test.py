# pyright: reportUnusedCallResult=false
"""File validation result and exception tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import config, exceptions, parser_exceptions
from define.compiler.data_structures import define_path
from define.compiler.validator import test_helpers as validator_test_helpers
from define.compiler.validator.structural import program_validator
from define.compiler.validator.structural.program_validator_tests import (
    test_helpers,
)


def test_successful_validation_returns_result_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert result.exception is None
    assert result.source_lines == source.splitlines()
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_parse_error_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = test_helpers.parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n",
        tmp_path,
        monkeypatch,
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.source_lines is not None
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_non_filesystem_parse_error_returns_single_result():
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(
            "defin the potential position<my.domain.com:my_lib:/bad>.\n"
        )
        .file_results
    )

    assert len(results) == 1
    result = results[0]
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.diagnostics == []


def test_invalid_utf8_populates_exception_and_source_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = test_helpers.parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff",
        tmp_path,
        monkeypatch,
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.source_lines is None
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_name_parser_error_at_definition_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<"
        + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
        + ">.\n"
    )
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.source_lines == source.splitlines()
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_name_parser_error_at_reference_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<mv:too:many:colons:bad:/y>.\n"
        "    }\n"
        "}\n"
    )
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.exception.context == "mv:too:many:colons:bad:/y"
    assert result.exception.line == 3
    assert result.exception.column == 29
    assert result.exception.file_path == PurePosixPath("test.dfn")


def test_config_error_populates_exception_and_root_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, config.ConfigError)
    assert result.file_path == define_path.DefinePath("test.dfn")
    assert result.root_prefix == define_path.EMPTY


def test_file_not_found_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validator_test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    relative_path = PurePosixPath("nonexistent.dfn")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, exceptions.SourceFileNotFoundError)
