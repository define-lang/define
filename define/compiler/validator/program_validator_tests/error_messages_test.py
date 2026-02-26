from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


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


def test_config_load_error_format_with_sub_root_fqun_mismatch_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    wrong_child_universe = "mv:define-lang.org:wrong_universe"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "it may only contain dimension points where {\n"
        f"it has the position<{child_universe}:/target>.\n"
        "}\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, parent_universe)
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", wrong_child_universe)
    _ = (tmp_path / "test.def").write_text(source, encoding="utf-8")
    _ = (tmp_path / "lib" / "target.def").write_text(
        f"define the potential position<{wrong_child_universe}:/target>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)

    formatted = diags[0].format(
        source.splitlines(),
        file_name=str(results[0].file_path),
    )
    assert formatted == (
        'File "test.def", line 3, column 21\n'
        + "it has the position<mv:define-lang.org:child:/target>.\n"
        + "                    ^\n"
        + "an error occurred while loading the project configuration:\n"
        + "Sub-root at 'lib' is configured as a dependency with universe "
        + "'mv:define-lang.org:child' but the actual project root in that path "
        + "says it has the universe name 'mv:define-lang.org:wrong_universe'"
    )
