"""Error message formatting tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.program_validator_tests.conftest import ValidateProject


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
        "    it may only contain dimension points where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
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
        'File "test.def", line 3, column 29\n'
        + "        it has the position<mv:define-lang.org:child:/target>.\n"
        + "                            ^\n"
        + "an error occurred while loading the project configuration:\n"
        + "Sub-root at 'lib' is configured as a dependency with universe "
        + "'mv:define-lang.org:child' but the actual project root in that path "
        + "says it has the universe name 'mv:define-lang.org:wrong_universe'"
    )


def test_local_duplicate_dimension_point_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a dimension point in position<pos>.\n"
        "        create a dimension point in position<pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 37\n"
        "        create a dimension point in position<pos>.\n"
        "                                    ^\n"
        "a dimension point already exists in 'position<pos>'; "
        "it was put there on line 7"
    )


def test_move_from_empty_position_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 37\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "                                    ^\n"
        "cannot move a dimension point from 'position<from_pos>'"
        " because it does not contain one"
    )


def test_deferred_position_chain_error_format(
    validate_project: ValidateProject,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</pos_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_project(
        {
            "test.def": source,
            "pos_b.def": (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong.def": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
        }
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert len(test_result.diagnostics) == 1
    assert isinstance(
        test_result.diagnostics[0], diagnostics.ChainElementNotInConstraintsDiagnostic
    )
    assert test_result.diagnostics[0].position.line == 10
    assert test_result.diagnostics[0].position.column == 72
    assert (
        test_result.diagnostics[0].element_name
        == "position<my.domain.com:my_lib:/wrong>"
    )
    assert (
        test_result.diagnostics[0].parent_name
        == "position<my.domain.com:my_lib:/pos_b>"
    )
    formatted = test_result.diagnostics[0].format(
        source.splitlines(), file_name="test.def"
    )
    assert formatted == (
        'File "test.def", line 10, column 72\n'
        "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "                                                                       ^\n"
        "'position<my.domain.com:my_lib:/wrong>' is not declared as one of the"
        " 'it has the' requirements in the definition of"
        " 'position<my.domain.com:my_lib:/pos_b>'"
    )


def test_deferred_action_chain_error_format(
    validate_project: ValidateProject,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the action</act_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_project(
        {
            "test.def": source,
            "act_b.def": (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c>.\n"
                "    it happens when {\n"
                "        the position<pos_c> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert len(test_result.diagnostics) == 1
    assert isinstance(
        test_result.diagnostics[0], diagnostics.ChainElementNotInActionDiagnostic
    )
    assert test_result.diagnostics[0].position.line == 10
    assert test_result.diagnostics[0].position.column == 70
    assert test_result.diagnostics[0].element_name == "position<no_such>"
    assert (
        test_result.diagnostics[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
    )
    formatted = test_result.diagnostics[0].format(
        source.splitlines(), file_name="test.def"
    )
    assert formatted == (
        'File "test.def", line 10, column 70\n'
        "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
        "                                                                     ^\n"
        "'position<no_such>' is not defined inside the definition of"
        " 'action<my.domain.com:my_lib:/act_b>'"
    )


def test_move_to_same_position_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a dimension point in position<pos>.\n"
        "        move the dimension point in position<pos> to position<pos>.\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 54\n"
        "        move the dimension point in position<pos> to position<pos>.\n"
        "                                                     ^\n"
        "source and destination cannot be identical when moving dimension points"
        " ('position<pos>' is the name of both"
        " the source and destination here)"
    )


def test_move_into_defining_position_format(
    validate_project: ValidateProject,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<local_pos> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</mid_pos>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<local_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<local_pos>"
        " to position<local_pos>::position</mid_pos>::position</end_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_project(
        {
            "test.def": source,
            "mid_pos.def": (
                "define the potential position<my.domain.com:my_lib:/mid_pos> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</end_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "end_pos.def": "define the potential position<my.domain.com:my_lib:/end_pos>.\n",
        }
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert len(test_result.diagnostics) == 1
    assert isinstance(
        test_result.diagnostics[0], diagnostics.MoveIntoDefiningPositionDiagnostic
    )
    assert test_result.diagnostics[0].position.line == 10
    assert test_result.diagnostics[0].position.column == 81
    assert test_result.diagnostics[0].from_position == "position<local_pos>"
    assert (
        test_result.diagnostics[0].to_position
        == "position<local_pos>::position</mid_pos>::position</end_pos>"
    )
    formatted = test_result.diagnostics[0].format(
        source.splitlines(), file_name="test.def"
    )
    assert formatted == (
        'File "test.def", line 10, column 81\n'
        "        move the dimension point in position<local_pos> to position<local_pos>::position</mid_pos>::position</end_pos>.\n"
        "                                                                                ^\n"
        "cannot move a dimension point\n"
        "  from: position<local_pos>\n"
        "    to: position<local_pos>::position</mid_pos>::position</end_pos>\n"
        "because the source position defines the destination position"
        " ('position<local_pos>' is the start of both positions)"
    )


def test_move_violates_constraints_error_message(
    validate_project: ValidateProject,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the position</x>.\n"
        "                it has the action</y>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_project(
        {
            "test.def": source,
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential action<my.domain.com:my_lib:/y> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 14
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "action<my.domain.com:my_lib:/y>",
        "position<my.domain.com:my_lib:/x>",
    ]
    formatted = all_diags[0].format(source.splitlines(), file_name="test.def")
    assert formatted == (
        'File "test.def", line 14, column 59\n'
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "                                                          ^\n"
        "cannot move a dimension point\n"
        "  from: position<from_pos>\n"
        "    to: position<to_pos>\n"
        "because the dimension point being moved does not have the required qualities:\n"
        "  action<my.domain.com:my_lib:/y>\n"
        "  position<my.domain.com:my_lib:/x>"
    )


def test_not_project_root_error_message_for_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    test_helpers.write_project_config(tmp_path, parent_universe)
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    (tmp_path / "lib").mkdir()
    _ = (tmp_path / "test.def").write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def"), max_workers=1
    )
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

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def"), max_workers=1
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("nonexistent.def")
    )
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

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
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

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    error = results[0].exception
    assert isinstance(error, exceptions.ConfigValidationError)
    assert str(error) == (
        'File ".define/project/config.defcl"\n'
        "Invalid configuration:\n"
        "  - project.universe_name: value is required"
    )
