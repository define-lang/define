"""Error message formatting tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

import textwrap
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import config, diagnostics, exceptions
from define.compiler.conftest import ValidateProject
from define.compiler.data_structures import define_path
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

# Keep Define source inline in this module because these tests compare rendered
# diagnostics against the exact source lines supplied to the formatter.


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
    assert formatted == textwrap.dedent("""\
        line 1, column 31
        define the potential position<standard:/path>.
                                      ^
        'standard' is a reserved universe name""")


def test_path_mismatch_format(validate_project: ValidateProject):
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    result = validate_project(
        {"foo/bar.dfn": source},
        entry_file="foo/bar.dfn",
    )
    assert len(result.program_result.file_results) == 1
    diags = result.program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "foo/bar.dfn", line 1, column 52
        define the potential position<my.domain.com:my_lib:/wrong/path>.
                                                           ^
        definition path '/wrong/path' does not match file path '/foo/bar'""")


def test_referenced_definition_not_found_format(validate_project: ValidateProject):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "target.dfn": (
                "define the potential action<my.domain.com:my_lib:/target> {\n"
                "    define the position<_noop>.\n"
                "    it happens when {\n"
                "        the position<_noop> has a particle.\n"
                "    } and it does {\n"
                "        define the position<__noop>.\n"
                "        create a particle in position<__noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert len(result.program_result.file_results) == 2
    test_result = result.program_result.file_results[0]
    assert test_result.file_path == define_path.DefinePath("test.dfn")
    diags = test_result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
                it has the position</target>.
                                    ^
        file 'target.dfn' does not contain a definition for 'position<my.domain.com:my_lib:/target>'""")
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
    assert formatted == textwrap.dedent("""\
        line 2, column 1
        define the potential position<my.domain.com:my_lib:/same>.
        ^
        duplicate position definition for path '/same'; first defined on line 1""")


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
    assert formatted == textwrap.dedent("""\
        line 2, column 1
        define the potential position<my.domain.com:my_lib:/same>.
        ^
        duplicate position definition for path '/same'; first defined on line 1""")


def test_move_to_same_position_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a particle in position<pos>.\n"
        "        move the particle in position<pos> to position<pos>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        line 8, column 47
                move the particle in position<pos> to position<pos>.
                                                      ^
        source and destination cannot be identical when moving particles ('position<pos>' is the name of both the source and destination here)""")
    )


def test_move_into_defining_position_format(validate_project: ValidateProject):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<local_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</mid_pos>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<local_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<local_pos> to position<local_pos>::position</mid_pos>::position</end_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "mid_pos.dfn": (
                "define the potential position<my.domain.com:my_lib:/mid_pos> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</end_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "end_pos.dfn": "define the potential position<my.domain.com:my_lib:/end_pos>.\n",
        },
    )
    assert len(result.program_result.file_results) == 3
    test_result = result.program_result.file_results[0]
    assert test_result.file_path == define_path.DefinePath("test.dfn")
    diags = test_result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[1], diagnostics.MoveIntoDefiningPositionDiagnostic)
    formatted = diags[1].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 10, column 74
                move the particle in position<local_pos> to position<local_pos>::position</mid_pos>::position</end_pos>.
                                                                                 ^
        cannot move a particle
          from: position<local_pos>
            to: position<local_pos>::position</mid_pos>::position</end_pos>
        because the source position defines the destination position ('position<local_pos>' is the start of both positions)""")
    )


def test_config_load_error_format_with_sub_root_fqun_mismatch_exception(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    wrong_child_universe = "mv:define-lang.org:wrong_universe"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "lib/target.dfn": f"define the potential position<{wrong_child_universe}:/target>.\n",
        },
        universe_name=parent_universe,
        local_deps={child_universe: "lib"},
        sub_roots={"lib": wrong_child_universe},
    )
    results = result.program_result.file_results
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, config.SubRootFqunMismatchError)

    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
                it has the position<mv:define-lang.org:child:/target>.
                                    ^
        an error occurred while loading the project configuration:
        Sub-root at 'lib' is configured as a dependency with universe 'mv:define-lang.org:child' but the actual project root in that path says it has the universe name 'mv:define-lang.org:wrong_universe'""")
    )


def test_not_project_root_error_message_for_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, config.NotProjectRootError)
    assert (
        str(error)
        == textwrap.dedent("""\
        The Define compiler must be run from a project root directory.
        A project root is any directory containing .define/project/config.defcl.
        For more information, see https://github.com/mkanat/define/define/docs/project-root.md""")
    )


def test_not_project_root_error_message_for_subroot(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {"test.dfn": source},
        universe_name=parent_universe,
        local_deps={child_universe: "lib"},
        max_workers=1,
    )
    results = result.program_result.file_results
    assert len(results) == 1
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, config.NotProjectRootError)
    assert (
        str(diags[0].error)
        == textwrap.dedent("""\
        The referenced subroot (lib) is not a valid project root: lib/.define/project/config.defcl not found.
        A project root is any directory containing lib/.define/project/config.defcl.
        For more information, see https://github.com/mkanat/define/define/docs/project-root.md""")
    )


def test_duplicate_fqun_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    parent_fqun = "mv:define-lang.org:parent"
    child_fqun = "mv:define-lang.org:child"
    source = (
        f"define the potential position<{parent_fqun}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_fqun}:/target>.\n"
        "    }\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, parent_fqun)
    test_helpers.write_local_deps_config(tmp_path, {child_fqun: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_fqun)
    test_helpers.write_local_deps_config(tmp_path / "lib", {parent_fqun: "nested"})
    test_helpers.write_sub_root(tmp_path, "lib/nested", parent_fqun)
    _ = (tmp_path / "test.dfn").write_text(source, encoding="utf-8")
    _ = (tmp_path / "lib" / "target.dfn").write_text(
        (
            f"define the potential position<{child_fqun}:/target> {{\n"
            "    it may only contain particles where {\n"
            f"        it has the position<{parent_fqun}:/leaf>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    _ = (tmp_path / "lib" / "nested" / "leaf.dfn").write_text(
        f"define the potential position<{parent_fqun}:/leaf>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"), max_workers=1)
        .file_results
    )
    assert len(results) == 2
    assert results[0].file_path == define_path.DefinePath("test.dfn")
    assert results[0].diagnostics == []
    assert results[1].file_path == define_path.DefinePath("lib/target.dfn")
    diags = results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, config.DuplicateFqunError)
    assert (
        str(diags[0].error)
        == textwrap.dedent("""\
        Universe 'mv:define-lang.org:parent' is already defined in '.define/project/config.defcl' and cannot be redefined in 'lib/nested/.define/project/config.defcl'""")
    )


def test_source_file_not_found_error_message(
    validate_project: ValidateProject,
):
    result = validate_project({}, entry_file="nonexistent.dfn")
    results = result.program_result.file_results
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.SourceFileNotFoundError)
    assert str(error) == "Source file not found: nonexistent.dfn"


def test_config_syntax_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        'project: {\n  universe_name "bad"\n}\n', encoding="utf-8"
    )
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, config.ConfigSyntaxError)
    assert str(error) == str(error.syntax_error)


def test_config_validation_error_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text("project: {}\n", encoding="utf-8")
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"))
        .file_results
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, config.ConfigValidationError)
    assert str(error) == textwrap.dedent("""\
        File ".define/project/config.defcl"
        Invalid configuration:
          - project.universe_name: value is required""")
