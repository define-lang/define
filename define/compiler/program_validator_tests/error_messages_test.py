from pathlib import Path, PurePosixPath

import pytest

from define.compiler import program_validator
from define.compiler.program_validator_tests import test_helpers


def test_reserved_universe_name_format():
    source = "define the potential position<standard:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 1, column 31\n"
        "define the potential position<standard:/path>.\n"
        "                              ^\n"
        "'standard' is a reserved universe name"
    )


def test_path_mismatch_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    source_path = tmp_path / "foo" / "bar.def"
    _ = source_path.parent.mkdir(parents=True, exist_ok=True)
    _ = source_path.write_text(source, encoding="utf-8")
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("foo/bar.def")
    )
    assert len(results) == 1
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(
        source.splitlines(), file_name=str(results[0].file_path)
    )
    assert formatted == (
        'File "foo/bar.def", line 1, column 52\n'
        "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
        "                                                   ^\n"
        "definition path '/wrong/path' does not match file path '/foo/bar'"
    )


def test_duplicate_definition_format():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 2, column 1\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "^\n"
        "duplicate position definition for path '/same'; "
        "first defined on line 1"
    )


def test_duplicate_definition_format_with_non_filesystem_file_name():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines(), str(results[0].file_path))
    assert formatted == (
        'File "<string>", line 2, column 1\n'
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "^\n"
        "duplicate position definition for path '/same'; "
        "first defined on line 1"
    )
