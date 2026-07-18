# pyright: reportUnusedCallResult=false
"""Global name walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path
from unittest import mock

import pytest

from define.compiler import config, diagnostics
from define.compiler.conftest import (
    ParseAndValidateFile,
    ValidateProject,
)
from define.compiler.data_structures import define_path
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import file_validator, program_validator
from define.compiler.validator.test_helpers import assert_no_errors


def test_nested_file_path(validate_project: ValidateProject):
    result = validate_project(
        {
            "sub/dir/leaf.dfn": "define the potential position<test.example.com:my_lib:/sub/dir/leaf>.\n",
        },
        universe_name="test.example.com:my_lib",
        entry_file="sub/dir/leaf.dfn",
    )
    assert len(result.file_results) == 1
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath(
        "sub/dir/leaf.dfn"
    )


def test_walk_returns_results_in_encounter_order(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<mv:define-lang.org:walk_order:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</middle>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential position<mv:define-lang.org:walk_order:/middle> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "leaf.dfn": "define the potential position<mv:define-lang.org:walk_order:/leaf>.\n",
        },
        universe_name="mv:define-lang.org:walk_order",
    )
    assert [r.file_path for r in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("middle.dfn"),
        define_path.DefinePath("leaf.dfn"),
    ]


def test_duplicate_does_not_corrupt_reference_resolution(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "root.dfn": (
                "define the potential position<my.domain.com:my_lib:/root> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</target>.\n"
                "        it has the position</dup>.\n"
                "    }\n"
                "}\n"
            ),
            "target.dfn": "define the potential position<my.domain.com:my_lib:/target>.\n",
            "dup.dfn": (
                "define the potential position<my.domain.com:my_lib:/target>.\n"
                "define the potential position<my.domain.com:my_lib:/dup>.\n"
            ),
        },
        entry_file="root.dfn",
        max_workers=1,
    )
    assert len(result.file_results) == 3
    assert result.file_results[0].file_path == define_path.DefinePath("root.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == define_path.DefinePath("dup.dfn")
    assert len(result.file_results[2].diagnostics) == 1
    assert isinstance(
        result.file_results[2].diagnostics[0], diagnostics.PathMismatchDiagnostic
    )
    assert result.file_results[2].diagnostics[0].location.line == 1
    assert result.file_results[2].diagnostics[0].location.column == 52
    assert result.file_results[2].diagnostics[0].expected_path == "/dup"
    assert result.file_results[2].diagnostics[0].actual_path == "/target"


def test_duplicate_source_definition_does_not_add_reference_edges(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test>.\n"
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
        },
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "position"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 1


def test_back_reference_to_earlier_definition_does_not_load_its_file(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
        },
    )
    assert len(result.file_results) == 1
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/test"
    assert diags[0].actual_path == "/other"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 52


def test_same_target_file_referenced_as_two_types_loads_once(
    validate_project: ValidateProject,
):
    original_validate_file = file_validator.FileStructuralValidator.validate_file
    validated_paths: list[str] = []

    def recording_validate_file(
        self: file_validator.FileStructuralValidator,
        context: file_validator.FileValidationContext,
    ):
        validated_paths.append(str(context.full_path))
        return original_validate_file(self, context)

    with mock.patch.object(
        file_validator.FileStructuralValidator,
        "validate_file",
        autospec=True,
        side_effect=recording_validate_file,
    ):
        result = validate_project(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</target>.\n"
                    "        it has the action</target>.\n"
                    "    }\n"
                    "}\n"
                ),
                "target.dfn": "define the potential position<my.domain.com:my_lib:/target>.\n",
            },
        )
    assert validated_paths == ["test.dfn", "target.dfn"]
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].file_path == "target.dfn"
    assert diags[0].definition_name == "action<my.domain.com:my_lib:/target>"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 27
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].diagnostics == []


def test_self_cycle_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</test>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<my.domain.com:my_lib:/test>\n"
        + "  --> position<my.domain.com:my_lib:/test>"
    )


def test_two_file_cycle_emits_diagnostic(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<mv:define-lang.org:test_walk_cycle:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</loop>.\n"
                "    }\n"
                "}\n"
            ),
            "loop.dfn": (
                "define the potential position<mv:define-lang.org:test_walk_cycle:/loop> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</test>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name="mv:define-lang.org:test_walk_cycle",
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("loop.dfn")
    assert result.file_results[1].exception is None
    diags = result.file_results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<mv:define-lang.org:test_walk_cycle:/test>",
        "position<mv:define-lang.org:test_walk_cycle:/loop>",
        "position<mv:define-lang.org:test_walk_cycle:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<mv:define-lang.org:test_walk_cycle:/test>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/loop>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/test>"
    )


_EXTERNAL_UNIVERSE_SOURCE = (
    "define the potential position<my.domain.com:my_lib:/test> {\n"
    "    it may only contain particles where {\n"
    "        it has the position<other.example.com:other_universe:/target>.\n"
    "    }\n"
    "}\n"
)


def test_external_universe_no_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].config_path == ".define/project/config.defcl"


def test_config_failure_still_validates_same_file_cycles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<my.domain.com:my_lib:/a> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "        it has the position</b>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/b> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</a>.\n"
        "    }\n"
        "}\n"
    )
    monkeypatch.chdir(tmp_path)
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].location.line == 9
    assert diags[0].location.column == 20
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/a>",
        "position<my.domain.com:my_lib:/b>",
        "position<my.domain.com:my_lib:/a>",
    ]
    assert isinstance(
        diags[1], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[1].location.line == 3
    assert diags[1].location.column == 29
    assert diags[1].universe == "other.example.com:other_universe"


def test_external_universe_without_local_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_external_universe_not_in_local_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(
        tmp_path, {"some.other.com:some_lib": "vendor/some_lib"}
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_external_universe_invalid_local_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    deps_dir = tmp_path / ".define" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    (deps_dir / "local.defcl").write_text(
        (
            "deps: {\n  local: [\n"
            '    { universe_name: "dup" path: "a" },\n'
            '    { universe_name: "dup" path: "b" }\n'
            "  ]\n}\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[0].error, config.ConfigValidationError)


def test_external_universe_configured_but_no_sub_root_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(
        tmp_path, {"other.example.com:other_universe": "vendor/other"}
    )
    (tmp_path / "vendor" / "other").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[0].error, config.NotProjectRootError)


def test_non_filesystem_current_universe_reference_does_not_load_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A current-universe reference from non-filesystem source is mishandled as
    # an unconfigured cross-universe reference (see
    # test_forward_reference_within_non_filesystem_source_is_broken in
    # file_not_found_test.py), so the on-disk file is never loaded.
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "target.dfn").write_text(
        "define the potential position<my.domain.com:my_lib:/target>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    assert str(result.file_results[0].file_path) == "<string>"
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "my.domain.com:my_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_unknown_universe_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_duplicate_unknown_universe_emits_one_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "        it has the position<other.example.com:other_universe:/another>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_unknown_universe_across_files_reported_per_file(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position<other.example.com:other_universe:/target>.\n"
                "        it has the position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential position<my.domain.com:my_lib:/other> {\n"
                "    it may only contain particles where {\n"
                "        it has the position<other.example.com:other_universe:/another>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 2
    for diag in all_diags:
        assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
        assert diag.location.line == 3
        assert diag.location.column == 29
        assert diag.universe == "other.example.com:other_universe"
        assert diag.current_universe_name == "my.domain.com:my_lib"


def test_already_tracked_discovery_does_not_skip_remaining_files(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</middle>.\n"
                "        it has the position</shared>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential position<my.domain.com:my_lib:/middle> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</shared>.\n"
                "        it has the position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "shared.dfn": "define the potential position<my.domain.com:my_lib:/shared>.\n",
            "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
        },
        max_workers=1,
    )
    assert len(result.file_results) == 4
    assert [r.file_path for r in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("middle.dfn"),
        define_path.DefinePath("shared.dfn"),
        define_path.DefinePath("leaf.dfn"),
    ]
    assert_no_errors(result)


def test_circular_reference_does_not_skip_remaining_edge_validation(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</test>.\n"
                "        it has the position</wrong_type>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong_type.dfn": (
                "define the potential action<my.domain.com:my_lib:/wrong_type> {\n"
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
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert isinstance(diags[1], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[1].file_path == "wrong_type.dfn"
    assert diags[1].definition_name == "position<my.domain.com:my_lib:/wrong_type>"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("wrong_type.dfn")
    assert result.file_results[1].diagnostics == []


def test_partial_local_deps_missing_still_validates_configured_sub_roots_non_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_a = "mv:define-lang.org:child_a"
    child_b = "mv:define-lang.org:child_b"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_a: "lib_a"})
    test_helpers.write_sub_root(tmp_path, "lib_a", child_a)
    (tmp_path / "lib_a/target_a.dfn").write_text(
        f"define the potential position<{child_a}:/target_a>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_a}:/target_a>.\n"
        f"        it has the position<{child_b}:/target_b>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert diags[0].universe == child_b
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert result.file_results[1].file_path.name == "target_a.dfn"
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_duplicate_unknown_universe_non_filesystem_does_not_skip_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<unknown.com:lib_a:/target_a>.\n"
        "        it has the position<unknown.com:lib_a:/target_b>.\n"
        "        it has the position<unknown.com:lib_b:/target_c>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].location.line == 5
    assert diags[1].location.column == 29


def test_unknown_universe_sharing_path_with_known_universe_does_not_load_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_universe = "mv:define-lang.org:child_lib"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_universe)
    (tmp_path / "lib" / "target.dfn").write_text(
        f"define the potential position<{child_universe}:/target>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<unknown.com:other_lib:/target>.\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    assert str(result.file_results[0].file_path) == "<string>"
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_unknown_universe_diagnostics_precede_sub_root_config_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_universe = "mv:define-lang.org:child_lib"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    (tmp_path / "lib").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        "        it has the position<unknown.com:other_lib:/other>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[1].error, config.NotProjectRootError)
    assert diags[1].location.line == 3
    assert diags[1].location.column == 29


def test_second_unknown_universe_for_same_path_diagnosed_per_definition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<unknown.com:lib_a:/target>.\n"
        "        it has the position<unknown.com:lib_b:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    # The second universe is diagnosed per-definition during edge validation,
    # so its diagnostic sorts before the file-level one for the first universe.
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_b"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_a"
    assert diags[1].current_universe_name == "my.domain.com:my_lib"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 29
