# pyright: reportUnusedCallResult=false
"""Global name walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.program_validator_tests.conftest import (
    ParseAndValidateFile,
    ValidateProject,
)


def test_nested_file_path(validate_project: ValidateProject):
    results = validate_project(
        {
            "sub/dir/leaf.def": "define the potential position<test.example.com:my_lib:/sub/dir/leaf>.\n",
        },
        universe_name="test.example.com:my_lib",
        entry_file="sub/dir/leaf.def",
    )
    assert len(results) == 1
    result = results[0]
    assert result.exception is None
    assert result.diagnostics == []
    assert result.file_path == PurePosixPath("sub/dir/leaf.def")


def test_walk_returns_results_in_encounter_order(validate_project: ValidateProject):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<mv:define-lang.org:walk_order:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</middle>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.def": (
                "define the potential position<mv:define-lang.org:walk_order:/middle> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "leaf.def": "define the potential position<mv:define-lang.org:walk_order:/leaf>.\n",
        },
        universe_name="mv:define-lang.org:walk_order",
    )
    assert [result.file_path for result in results] == [
        PurePosixPath("test.def"),
        PurePosixPath("middle.def"),
        PurePosixPath("leaf.def"),
    ]


def test_duplicate_does_not_corrupt_reference_resolution(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "root.def": (
                "define the potential position<my.domain.com:my_lib:/root> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</target>.\n"
                "        it has the position</dup>.\n"
                "    }\n"
                "}\n"
            ),
            "target.def": "define the potential position<my.domain.com:my_lib:/target>.\n",
            "dup.def": (
                "define the potential position<my.domain.com:my_lib:/target>.\n"
                "define the potential position<my.domain.com:my_lib:/dup>.\n"
            ),
        },
        entry_file="root.def",
        max_workers=1,
    )
    assert len(results) == 3
    assert results[0].file_path == PurePosixPath("root.def")
    assert results[0].diagnostics == []
    assert results[1].file_path == PurePosixPath("target.def")
    assert results[1].diagnostics == []
    assert results[2].file_path == PurePosixPath("dup.def")
    assert len(results[2].diagnostics) == 1
    assert isinstance(results[2].diagnostics[0], diagnostics.PathMismatchDiagnostic)
    assert results[2].diagnostics[0].position.line == 1
    assert results[2].diagnostics[0].position.column == 52
    assert results[2].diagnostics[0].expected_path == "/dup"
    assert results[2].diagnostics[0].actual_path == "/target"


def test_duplicate_source_definition_does_not_add_reference_edges(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test>.\n"
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</test>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "position"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].position.line == 2
    assert all_diags[0].position.column == 1


def test_self_cycle_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
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
    assert diags[0].position.line == 3
    assert diags[0].position.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<my.domain.com:my_lib:/test>\n"
        + "  --> position<my.domain.com:my_lib:/test>"
    )


def test_two_file_cycle_emits_diagnostic(validate_project: ValidateProject):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<mv:define-lang.org:test_walk_cycle:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</loop>.\n"
                "    }\n"
                "}\n"
            ),
            "loop.def": (
                "define the potential position<mv:define-lang.org:test_walk_cycle:/loop> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</test>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name="mv:define-lang.org:test_walk_cycle",
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert results[0].diagnostics == []
    assert results[1].file_path == PurePosixPath("loop.def")
    assert results[1].exception is None
    diags = results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<mv:define-lang.org:test_walk_cycle:/test>",
        "position<mv:define-lang.org:test_walk_cycle:/loop>",
        "position<mv:define-lang.org:test_walk_cycle:/test>",
    ]
    assert diags[0].position.line == 3
    assert diags[0].position.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<mv:define-lang.org:test_walk_cycle:/test>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/loop>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/test>"
    )


_EXTERNAL_UNIVERSE_SOURCE = (
    "define the potential position<my.domain.com:my_lib:/test> {\n"
    "    it may only contain dimension points where {\n"
    "        it has the position<other.example.com:other_universe:/target>.\n"
    "    }\n"
    "}\n"
)


def test_external_universe_no_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].config_path == ".define/project/config.defcl"


def test_external_universe_without_local_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
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
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
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
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.ConfigValidationError)


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
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(_EXTERNAL_UNIVERSE_SOURCE)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)


def test_unknown_universe_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_duplicate_unknown_universe_emits_one_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "        it has the position<other.example.com:other_universe:/another>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_unknown_universe_across_files_reported_per_file(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position<other.example.com:other_universe:/target>.\n"
                "        it has the position</other>.\n"
                "    }\n"
                "}\n"
            ),
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position<other.example.com:other_universe:/another>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 2
    for diag in all_diags:
        assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
        assert diag.position.line == 3
        assert diag.position.column == 29
        assert diag.universe == "other.example.com:other_universe"
        assert diag.current_universe_name == "my.domain.com:my_lib"


def test_already_tracked_discovery_does_not_skip_remaining_files(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</middle>.\n"
                "        it has the position</shared>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.def": (
                "define the potential position<my.domain.com:my_lib:/middle> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</shared>.\n"
                "        it has the position</leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "shared.def": "define the potential position<my.domain.com:my_lib:/shared>.\n",
            "leaf.def": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
        },
        max_workers=1,
    )
    assert len(results) == 4
    assert [r.file_path for r in results] == [
        PurePosixPath("test.def"),
        PurePosixPath("middle.def"),
        PurePosixPath("shared.def"),
        PurePosixPath("leaf.def"),
    ]
    assert all(r.diagnostics == [] for r in results)


def test_circular_reference_does_not_skip_remaining_edge_validation(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</test>.\n"
                "        it has the position</wrong_type>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong_type.def": "define the potential action<my.domain.com:my_lib:/wrong_type>.\n",
        },
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].position.line == 3
    assert diags[0].position.column == 20
    assert isinstance(diags[1], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diags[1].path == "/wrong_type"
    assert diags[1].expected_type == "position"
    assert diags[1].position.line == 4
    assert diags[1].position.column == 29
    assert results[1].file_path == PurePosixPath("wrong_type.def")
    assert results[1].diagnostics == []


def test_duplicate_unknown_universe_non_filesystem_does_not_skip_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position<unknown.com:lib_a:/target_a>.\n"
        "        it has the position<unknown.com:lib_a:/target_b>.\n"
        "        it has the position<unknown.com:lib_b:/target_c>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].position.line == 5
    assert diags[1].position.column == 29
