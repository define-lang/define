"""Error message formatting tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.

Message format tests exist only for complex diagnostics, such as multi-line
messages or messages with many fields. Behavioral tests cover simple ones.
"""

from __future__ import annotations

import textwrap
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.data_structures import define_path
from define.compiler.errors import (
    diagnostics,
    exceptions,
    parser_exceptions,
    source_map,
)
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator
from define.compiler.validator.structural.program_validator_tests import (
    test_helpers as program_validator_test_helpers,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from define.compiler.conftest import ValidateProject

# Keep Define source inline in this module because these tests compare rendered
# diagnostics against the exact source lines supplied to the formatter.


def test_reserved_universe_name_format():
    source = "define the potential position<standard:/path>.\n"
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 1, column 31
            define the potential position<standard:/path>.
                                          ^^^^^^^^
        'standard' is a reserved universe name""")


def test_invalid_fqun_format_format(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position<mv:too:many:colons:bad:/y>.\n"
                "    }\n"
                "}\n"
            )
        }
    )
    exception = result.program_result.file_results[0].exception
    assert isinstance(exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert (
        exception.format(result.program_result.source_map)
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
            it has the position<mv:too:many:colons:bad:/y>.
                                ^^^^^^^^^^^^^^^^^^^^^^
        Fully qualified universe name format is invalid. Use '<multiverse:authority:universe:/path>' or '<authority:universe:/path>' or '<standard:/path>'.""")
    )


def test_path_mismatch_format(validate_project: ValidateProject):
    source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
    result = validate_project(
        {"foo/bar.dfn": source},
        entry_file="foo/bar.dfn",
    )
    assert len(result.program_result.file_results) == 1
    diags = result.program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(result.program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File "foo/bar.dfn", line 1, column 52
            define the potential position<my.domain.com:my_lib:/wrong/path>.
                                                               ^^^^^^^^^^^
        definition path '/wrong/path' does not match file path '/foo/bar'""")


def test_circular_reference_format(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential position<my.domain.com:my_lib:/other> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</test>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File "other.dfn", line 3, column 20
            it has the position</test>.
                       ^^^^^^^^^^^^^^^
        circular references between definitions are not allowed in Define:
        position<my.domain.com:my_lib:/test>
          --> position<my.domain.com:my_lib:/other>
          --> position<my.domain.com:my_lib:/test>""")


def test_incorrect_indentation_format(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "      it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 3, column 1
                  it has the position</child>.
            ^^^^^^
        expected 8 spaces of indentation on this line, but found 6""")


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
    formatted = diags[0].format(result.program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 20
            it has the position</target>.
                       ^^^^^^^^^^^^^^^^^
        file 'target.dfn' does not contain a definition for 'position<my.domain.com:my_lib:/target>'""")
    )


def test_referenced_file_not_found_format(validate_project: ValidateProject):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project({"test.dfn": source})
    diags = result.program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    formatted = diags[0].format(result.program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
            it has the position</missing>.
                                ^^^^^^^^
        there is no file 'missing.dfn' in this project""")


def test_path_inside_other_universe_format(validate_project: ValidateProject):
    parent_universe = "mv:define-lang.org:parent"
    child_universe = "mv:define-lang.org:child"
    source = (
        f"define the potential position<{parent_universe}:/test> {{\n"
        "    it may only contain particles where {\n"
        "        it has the position</lib/parent_target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "lib/parent_target.dfn": f"define the potential position<{parent_universe}:/lib/parent_target>.\n",
        },
        universe_name=parent_universe,
        local_deps={child_universe: "lib"},
        sub_roots={"lib": child_universe},
    )
    diags = result.program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathInsideOtherUniverseDiagnostic)
    formatted = diags[0].format(result.program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
            it has the position</lib/parent_target>.
                                ^^^^^^^^^^^^^^^^^^
        the path 'lib/parent_target.dfn' is inside of a different universe from this one ('mv:define-lang.org:child' located at 'lib') ; two different universes cannot both occupy 'lib'""")
    )


def test_external_universe_not_configured_format(validate_project: ValidateProject):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project({"test.dfn": source})
    diags = result.program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    formatted = diags[0].format(result.program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 3, column 29
            it has the position<other.example.com:other_universe:/target>.
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        universe 'other.example.com:other_universe' is not configured as a dependency of this universe (my.domain.com:my_lib); add it to .define/deps/local.defcl""")
    )


def test_standard_definition_not_found_format():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<standard:/missing>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.StandardDefinitionNotFoundDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 3, column 20
            it has the position<standard:/missing>.
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
        the standard universe does not define 'position<standard:/missing>'""")


def test_unreferenced_position_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<unused>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 5, column 20
            define the position<unused>.
                       ^^^^^^^^^^^^^^^^
        'position<unused>' is defined here, but it is never referenced within this definition; either remove the definition or reference 'position<unused>'.""")
    )


def test_local_position_name_conflict_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        define the position<pos>.\n"
        "        create a particle in position<pos>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 6, column 20
            define the position<pos>.
                       ^^^^^^^^^^^^^
        duplicate local definition 'pos'; first defined on line 5""")


def test_duplicate_definition_format():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 2, column 1
            define the potential position<my.domain.com:my_lib:/same>.
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        duplicate position definition for path '/same'; first defined on line 1""")


def test_duplicate_logical_operation_support_format():
    source = (
        "define the potential value<my.domain.com:my_lib:/number> {\n"
        "    it supports the logical_operation<standard:/number/add> {\n"
        "        it may be read.\n"
        "    }\n"
        "    it supports the logical_operation<standard:/number/add> {\n"
        "        it may be written.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 5, column 21
            it supports the logical_operation<standard:/number/add> {
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        'logical_operation<standard:/number/add>' is already supported on line 2; each logical operation may be listed only once in a value definition""")
    )


def test_logical_operation_support_order_format():
    source = (
        "define the potential value<my.domain.com:my_lib:/number> {\n"
        "    it supports the logical_operation<standard:/text/less_than> {\n"
        "        it may be read.\n"
        "    }\n"
        "    it supports the logical_operation<standard:/number/add> {\n"
        "        it may be read.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 5, column 21
            it supports the logical_operation<standard:/number/add> {
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        'logical_operation<standard:/number/add>' is out of order; Logical Operation Support Statements must be in alphabetical order by logical operation name, so it must come before 'logical_operation<standard:/text/less_than>'""")
    )


def test_local_view_error_messages():
    source = (
        "define the operation<my.domain.com:my_lib:/test> {\n"
        "    it does {\n"
        "        define the view<unused> {\n"
        "            it may only contain particles where {\n"
        "                it has the encoding<standard:/number/decimal/ascii>.\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    formatted = [
        diagnostic.format(program_result.source_map)
        for diagnostic in program_result.file_results[0].diagnostics
    ]
    assert formatted == [
        textwrap.dedent("""\
        line 2, column 5
            it does {
            ^^^^^^^^^
        a value operation must execute at least one logical operation or value operation"""),
        textwrap.dedent("""\
        line 3, column 20
            define the view<unused> {
                       ^^^^^^^^^^^^
        'view<unused>' must have a value quality, because every local view must have one"""),
        textwrap.dedent("""\
        line 3, column 20
            define the view<unused> {
                       ^^^^^^^^^^^^
        'view<unused>' is defined here, but it is never referenced within this definition; either remove the definition or reference 'view<unused>'."""),
        textwrap.dedent("""\
        line 5, column 28
            it has the encoding<standard:/number/decimal/ascii>.
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        local views may only be assigned a value quality. However, 'encoding<standard:/number/decimal/ascii>' is not a value quality"""),
    ]


def test_non_filesystem_diagnostics_have_no_file_name():
    source = (
        "define the potential position<my.domain.com:my_lib:/same>.\n"
        "define the potential position<my.domain.com:my_lib:/same>.\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    assert diags[0].location.file_path is None
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 2, column 1
            define the potential position<my.domain.com:my_lib:/same>.
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        duplicate position definition for path '/same'; first defined on line 1""")


def test_move_to_same_position_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a particle in position<pos>.\n"
        "        move the particle in position<pos> to position<pos>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 7, column 47
            move the particle in position<pos> to position<pos>.
                                                  ^^^^^^^^^^^^^
        source and destination cannot be identical when moving particles ('position<pos>' is the name of both the source and destination here)""")
    )


def test_invalid_local_name_character_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<my-pos>.\n"
        "        create a particle in position<my-pos>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 5, column 31
            define the position<my-pos>.
                                  ^
        invalid character '-' in local name 'my-pos'""")


def test_invalid_local_name_characters_format():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<Bad-Name>.\n"
        "        create a particle in position<Bad-Name>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        line 5, column 29
            define the position<Bad-Name>.
                                ^
        invalid characters 'B', '-' and 'N' in local name 'Bad-Name'""")


def test_move_into_defining_position_format(validate_project: ValidateProject):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<local_pos> {\n"
        "            it may only contain particles where {\n"
        "                it has the position</mid_pos>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<local_pos>.\n"
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
    formatted = diags[1].format(result.program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 11, column 74
            move the particle in position<local_pos> to position<local_pos>::position</mid_pos>::position</end_pos>.
                                                                             ^^^^^^^^^^^^^^^^^^
        cannot move a particle
          from: position<local_pos>
            to: position<local_pos>::position</mid_pos>::position</end_pos>
        because the source position defines the destination position ('position<local_pos>' is the start of both positions)""")
    )


def test_sub_root_fqun_mismatch_error_message(
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
    program_result = result.program_result
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.SubRootFqunMismatchDiagnostic)
    assert (
        diagnostic.format(program_result.source_map)
        == 'File "lib/.define/project/config.defcl"\n'
        + "Sub-root at 'lib' is configured as a dependency with universe 'mv:define-lang.org:child' but the actual project root in that path says it has the universe name 'mv:define-lang.org:wrong_universe'"
    )


def test_invalid_config_format_for_supplied_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    deps_path = tmp_path / ".define" / "deps" / "local.defcl"
    deps_path.parent.mkdir(parents=True)
    _ = deps_path.write_text(
        "deps: {\n  local: [\n    {}\n  ]\n}\n", encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.InvalidConfigDiagnostic)

    formatted = diagnostic.format(program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File ".define/deps/local.defcl"
        Invalid configuration:
          - deps.local.universe_name: value is required
          - deps.local.path: value is required""")


def test_external_universe_not_configured_format_for_supplied_source_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 3, column 29
            it has the position<other.example.com:other_universe:/target>.
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        universe 'other.example.com:other_universe' is not configured as a dependency of this universe (my.domain.com:my_lib); add it to .define/deps/local.defcl""")
    )


def test_no_project_root_format_for_supplied_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 3, column 29
            it has the position<other.example.com:other_universe:/target>.
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        universe 'other.example.com:other_universe' was not previously defined, so the compiler tried to load it from the filesystem. However, .define/project/config.defcl was not found.
        For more information, see https://github.com/mkanat/define/define/docs/project-root.md""")
    )


def test_no_project_root_for_definition_not_in_supplied_source_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the action</other>.\n"
        "    }\n"
        "}\n"
    )
    program_result = program_validator.validate_program_non_filesystem(source)
    diags = program_result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic
    )
    formatted = diags[0].format(program_result.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        line 3, column 20
            it has the action</other>.
                       ^^^^^^^^^^^^^^
        'action</other>' is not defined in the supplied source, so the compiler tried to load it from the project. However, .define/project/config.defcl was not found.
        For more information, see https://github.com/mkanat/define/define/docs/project-root.md""")
    )


def test_not_project_root_error_message_for_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    program_result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.NotRunFromProjectRootDiagnostic)
    assert (
        diagnostic.format(program_result.source_map)
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
    program_result = result.program_result
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.SubRootNotProjectRootDiagnostic)
    assert (
        diagnostic.format(program_result.source_map)
        == textwrap.dedent("""\
        The referenced subroot (lib) is not a valid project root: lib/.define/project/config.defcl not found.
        A project root is any directory containing lib/.define/project/config.defcl.
        For more information, see https://github.com/mkanat/define/define/docs/project-root.md""")
    )


def test_sub_root_path_already_declared_error_message(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    result = validate_project(
        {"test.dfn": f"define the potential position<{parent_universe}:/test>.\n"},
        universe_name=parent_universe,
        local_deps={
            "mv:define-lang.org:first_child": "lib",
            "mv:define-lang.org:second_child": "lib",
        },
    )
    program_result = result.program_result
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.SubRootPathAlreadyDeclaredDiagnostic)
    assert diagnostic.format(program_result.source_map) == textwrap.dedent("""\
        File ".define/deps/local.defcl"
        Two local dependencies declare the sub-root 'lib':
          ".define/deps/local.defcl" declares universe 'mv:define-lang.org:first_child' at 'lib'
          ".define/deps/local.defcl" declares universe 'mv:define-lang.org:second_child' at 'lib'
        Only the first one is used.""")


def test_local_dependency_on_own_universe_error_message(
    validate_project: ValidateProject,
):
    parent_universe = "mv:define-lang.org:parent"
    result = validate_project(
        {"test.dfn": f"define the potential position<{parent_universe}:/test>.\n"},
        universe_name=parent_universe,
        local_deps={parent_universe: "lib"},
    )
    program_result = result.program_result
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.LocalDependencyOnOwnUniverseDiagnostic)
    assert diagnostic.format(program_result.source_map) == (
        'File ".define/deps/local.defcl"\n'
        + "\".define/deps/local.defcl\" declares universe 'mv:define-lang.org:parent' at 'lib', but that is the project's own universe, so it cannot be a dependency of that project."
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
    test_helpers.write_project_config(tmp_path / "lib", child_fqun)
    test_helpers.write_local_deps_config(tmp_path / "lib", {parent_fqun: "nested"})
    test_helpers.write_project_config(tmp_path / "lib" / "nested", parent_fqun)
    _ = (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
    _ = (tmp_path / "lib" / "target.dfn").write_text(
        (
            f"define the potential position<{child_fqun}:/target> {{\n"
            "    it may only contain particles where {\n"
            f"        it has the position<{parent_fqun}:/leaf>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    _ = (tmp_path / "lib" / "nested" / "leaf.dfn").write_text(
        f"define the potential position<{parent_fqun}:/leaf>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    program_result = program_validator.validate_program(
        PurePosixPath("test.dfn"), max_workers=1
    )
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.DuplicateFqunDiagnostic)
    assert (
        diagnostic.format(program_result.source_map)
        == textwrap.dedent("""\
        File "lib/nested/.define/project/config.defcl"
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
        'project: {\n  universe_name "bad"\n}\n', encoding="utf-8", newline="\n"
    )
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    program_result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.ConfigDclDiagnostic)
    assert diagnostic.format(program_result.source_map) == textwrap.dedent("""\
        File ".define/project/config.defcl", line 2, column 16
            universe_name "bad"
                         ^
        Missing colon after field name""")


def test_config_schema_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        'project: {\n  universe_name: "x.com:lib"\n  owner: "y"\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    program_result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.ConfigDclDiagnostic)
    assert diagnostic.format(program_result.source_map) == textwrap.dedent("""\
        File ".define/project/config.defcl", line 3, column 3
            owner: "y"
            ^^^^^
        owner: define.config.project.Project has no field with this name""")


def test_config_validation_error_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        "project: {}\n", encoding="utf-8", newline="\n"
    )
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    program_result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert program_result.all_exceptions == []
    (diagnostic,) = program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.InvalidConfigDiagnostic)
    assert diagnostic.format(program_result.source_map) == textwrap.dedent("""\
        File ".define/project/config.defcl"
        Invalid configuration:
          - project.universe_name: value is required""")


def test_invalid_utf8_error_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    result = program_validator_test_helpers.parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/test>.\n# caf\xe9\n",
        tmp_path,
        monkeypatch,
    )

    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.source_digest is not None
    sources = source_map.SourceMap(
        {PurePosixPath("test.dfn"): result.source_digest}, in_memory_source=None
    )
    assert result.exception.format(sources) == textwrap.dedent("""\
        File "test.dfn", line 2, column 6
            # caf\ufffd
                 ^
        Invalid UTF-8 byte sequence: (\\xe9).""")
