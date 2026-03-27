"""Error message formatting tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.conftest import ValidateProject
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator


def test_reserved_universe_name_format():
    source = "define the potential position<standard:/path>.\n"
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
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


def test_path_mismatch_format(validate_project: ValidateProject):
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    result = validate_project(
        {"foo/bar.def": source},
        entry_file="foo/bar.def",
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
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
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
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


def test_non_filesystem_diagnostics_have_no_file_name():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert diags[0].location.file_path is None
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 2, column 1\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "^\n"
        "duplicate position definition for path '/same'; "
        "first defined on line 1"
    )


def test_config_load_error_format_with_sub_root_fqun_mismatch_exception(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    wrong_child_universe = "mv:define-lang.org:wrong_universe"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "    it may only contain dimension points where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.def": source,
            "lib/target.def": f"define the potential position<{wrong_child_universe}:/target>.\n",
        },
        universe_name=parent_universe,
        local_deps={child_universe: "lib"},
        sub_roots={"lib": wrong_child_universe},
    )
    results = result.file_results
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)

    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.def", line 3, column 29\n'
        + "        it has the position<mv:define-lang.org:child:/target>.\n"
        + "                            ^\n"
        + "an error occurred while loading the project configuration:\n"
        + "Sub-root at 'lib' is configured as a dependency with universe "
        + "'mv:define-lang.org:child' but the actual project root in that path "
        + "says it has the universe name 'mv:define-lang.org:wrong_universe'"
    )


def test_not_project_root_error_message_for_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.def"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.NotProjectRootError)
    assert str(error) == (
        "The Define compiler must be run from a project root directory.\n"
        "A project root is any directory containing .define/project/config.defcl.\n"
        "For more information, see https://github.com/mkanat/define/define/docs/project-root.md"
    )


def test_not_project_root_error_message_for_subroot(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "    it may only contain dimension points where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {"test.def": source},
        universe_name=parent_universe,
        local_deps={child_universe: "lib"},
        max_workers=1,
    )
    results = result.file_results
    assert len(results) == 1
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)
    assert str(diags[0].error) == (
        "The referenced subroot (lib) is not a valid project root:"
        " lib/.define/project/config.defcl not found.\n"
        "A project root is any directory containing lib/.define/project/config.defcl.\n"
        "For more information, see https://github.com/mkanat/define/define/docs/project-root.md"
    )


def test_duplicate_fqun_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    parent_fqun = "mv:define-lang.org:parent"
    child_fqun = "mv:define-lang.org:child"
    source = (
        f"define the potential position<{parent_fqun}:/test> {{\n"
        "    it may only contain dimension points where {\n"
        f"        it has the position<{child_fqun}:/target>.\n"
        "    }\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, parent_fqun)
    test_helpers.write_local_deps_config(tmp_path, {child_fqun: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_fqun)
    test_helpers.write_local_deps_config(tmp_path / "lib", {parent_fqun: "nested"})
    test_helpers.write_sub_root(tmp_path, "lib/nested", parent_fqun)
    _ = (tmp_path / "test.def").write_text(source, encoding="utf-8")
    _ = (tmp_path / "lib" / "target.def").write_text(
        (
            f"define the potential position<{child_fqun}:/target> {{\n"
            "    it may only contain dimension points where {\n"
            f"        it has the position<{parent_fqun}:/leaf>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    _ = (tmp_path / "lib" / "nested" / "leaf.def").write_text(
        f"define the potential position<{parent_fqun}:/leaf>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.def"), max_workers=1)
        .file_results
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].diagnostics == []
    assert results[1].file_path == PurePosixPath("lib/target.def")
    diags = results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, exceptions.DuplicateFqunError)
    assert str(diags[0].error) == (
        "Universe 'mv:define-lang.org:parent' is already defined in"
        " '.define/project/config.defcl'"
        " and cannot be redefined in 'lib/nested/.define/project/config.defcl'"
    )


def test_source_file_not_found_error_message(
    validate_project: ValidateProject,
):
    result = validate_project({}, entry_file="nonexistent.def")
    results = result.file_results
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.SourceFileNotFoundError)
    assert str(error) == "Source file not found: nonexistent.def"


def test_config_syntax_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        'project: {\n  universe_name "bad"\n}\n', encoding="utf-8"
    )
    _ = (tmp_path / "test.def").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.def"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.ConfigSyntaxError)
    assert str(error) == str(error.syntax_error)


def test_config_validation_error_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text("project: {}\n", encoding="utf-8")
    _ = (tmp_path / "test.def").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.def"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.ConfigValidationError)
    assert str(error) == (
        'File ".define/project/config.defcl"\n'
        "Invalid configuration:\n"
        "  - project.universe_name: value is required"
    )
