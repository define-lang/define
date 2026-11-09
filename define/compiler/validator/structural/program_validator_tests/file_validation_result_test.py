# pyright: reportUnusedCallResult=false
"""File validation result and exception tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.validator import test_helpers as validator_test_helpers
from define.compiler.validator.structural import program_validator
from define.compiler.validator.structural.program_validator_tests import (
    test_helpers,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_successful_validation_returns_result_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert result.load_failure is None
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_parse_error_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = test_helpers.parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n",
        tmp_path,
        monkeypatch,
    )

    assert result.diagnostics == [result.load_failure]
    assert isinstance(result.load_failure, syntax_errors.DefineSyntaxError)
    assert result.file_path == define_path.DefinePath("test.dfn")


def test_non_filesystem_parse_error_returns_single_result():
    results = program_validator.validate_program_non_filesystem(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n"
    ).file_results

    assert len(results) == 1
    result = results[0]
    assert isinstance(result.load_failure, syntax_errors.DefineSyntaxError)
    assert result.diagnostics == [result.load_failure]


def test_invalid_utf8_populates_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff"
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == [result.load_failure]
    assert isinstance(result.load_failure, syntax_errors.InvalidEncodingError)
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

    assert result.diagnostics == [result.load_failure]
    assert isinstance(result.load_failure, syntax_errors.GlobalNameInvalidFqunFormat)
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

    assert result.diagnostics == [result.load_failure]
    assert isinstance(result.load_failure, syntax_errors.GlobalNameInvalidFqunFormat)
    assert result.load_failure.location.line == 3
    assert result.load_failure.location.column == 29
    assert result.load_failure.location.end_column == 50
    assert result.load_failure.location.file_path == "test.dfn"


def test_file_not_found_populates_load_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validator_test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    relative_path = PurePosixPath("nonexistent.dfn")
    monkeypatch.chdir(tmp_path)
    results = program_validator.validate_program(relative_path).file_results
    assert len(results) == 1
    result = results[0]

    assert result.load_failure == diagnostics.SourceFileNotFoundDiagnostic(
        file_path="nonexistent.dfn"
    )
