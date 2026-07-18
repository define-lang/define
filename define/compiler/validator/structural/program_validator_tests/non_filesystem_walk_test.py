# pyright: reportUnusedCallResult=false
"""Non-filesystem cross-file walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path

import pytest

from define.compiler import config, diagnostics
from define.compiler.data_structures import define_path
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors

_PARENT_UNIVERSE = "mv:define-lang.org:parent_universe"
_CHILD_UNIVERSE = "mv:define-lang.org:child_universe"


def test_external_universe_no_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
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
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
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
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(
        tmp_path, {"some.other.com:some_lib": "vendor/some_lib"}
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
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
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
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
        .validate_program_non_filesystem(source)
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
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.example.com:other_universe:/target>.\n"
        "    }\n"
        "}\n"
    )
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(
        tmp_path, {"other.example.com:other_universe": "vendor/other"}
    )
    (tmp_path / "vendor" / "other").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[0].error, config.NotProjectRootError)


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


def test_non_filesystem_reference_walks_into_sub_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, _PARENT_UNIVERSE)
    test_helpers.write_local_deps_config(tmp_path, {_CHILD_UNIVERSE: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    (tmp_path / "lib/target.dfn").write_text(
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/target> {{\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</leaf>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib/leaf.dfn").write_text(
        f"define the potential position<{_CHILD_UNIVERSE}:/leaf>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[2].file_path == define_path.DefinePath("lib/leaf.dfn")
    assert result.file_results[2].root_prefix == define_path.DefinePath("lib")


def test_non_filesystem_cross_universe_reference(
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
        f"        it has the position<{child_universe}:/target>.\n"
        f"        it has the position<{child_universe}:/missing>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "lib/missing.dfn"
    assert diag.location.line == 4
    assert diag.location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_unknown_universe_does_not_block_known_universe_for_same_path(
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
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].diagnostics == []


def test_unknown_universe_and_sub_root_config_errors_in_source_order(
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
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, config.NotProjectRootError)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:other_lib"
    assert diags[1].current_universe_name == "my.domain.com:my_lib"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29


def test_two_unknown_universes_for_same_path_each_diagnosed(
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
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].current_universe_name == "my.domain.com:my_lib"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29


def test_two_known_universes_for_same_path_each_load_their_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_x = "mv:define-lang.org:child_x"
    child_y = "mv:define-lang.org:child_y"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_x: "lib_x", child_y: "lib_y"})
    test_helpers.write_sub_root(tmp_path, "lib_x", child_x)
    test_helpers.write_sub_root(tmp_path, "lib_y", child_y)
    (tmp_path / "lib_x" / "target.dfn").write_text(
        (
            f"define the potential position<{child_x}:/target> {{\n"
            "    it may only contain particles where {\n"
            "        it has the position</x_child>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib_x" / "x_child.dfn").write_text(
        f"define the potential position<{child_x}:/x_child>.\n",
        encoding="utf-8",
    )
    (tmp_path / "lib_y" / "target.dfn").write_text(
        (
            f"define the potential position<{child_y}:/target> {{\n"
            "    it may only contain particles where {\n"
            "        it has the position</y_child>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib_y" / "y_child.dfn").write_text(
        f"define the potential position<{child_y}:/y_child>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_x}:/target>.\n"
        f"        it has the position<{child_y}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source, max_workers=1
        )
    )
    assert len(result.file_results) == 5
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib_x/target.dfn"
    )
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib_x")
    assert (
        result.file_results[1]
        .definition_results[0]
        .definition.typed_name.full_typed_name
        == f"position<{child_x}:/target>"
    )
    assert result.file_results[2].file_path == define_path.DefinePath(
        "lib_y/target.dfn"
    )
    assert result.file_results[2].root_prefix == define_path.DefinePath("lib_y")
    assert (
        result.file_results[2]
        .definition_results[0]
        .definition.typed_name.full_typed_name
        == f"position<{child_y}:/target>"
    )
    assert result.file_results[3].file_path == define_path.DefinePath(
        "lib_x/x_child.dfn"
    )
    assert result.file_results[4].file_path == define_path.DefinePath(
        "lib_y/y_child.dfn"
    )


def test_forward_reference_within_non_filesystem_source_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Define requires definitions to appear before they are referenced; a forward
    # ref within one source is not recognized as same-file and the validator
    # mishandles it as an unconfigured cross-universe reference to the current
    # universe.
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/a> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</b>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/b>.\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    diag = diags[0]
    assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diag.universe == "my.domain.com:my_lib"
    assert diag.current_universe_name == "my.domain.com:my_lib"
    assert diag.location.line == 3
    assert diag.location.column == 29


@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason=(
        "Non-filesystem resolution routes every reference through local deps,"
        " and a project's own universe is never among its local deps, so a"
        " current-universe reference is diagnosed as an unconfigured external"
        " universe instead of resolving to the file on disk."
    ),
)
def test_non_filesystem_reference_walks_into_current_universe_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    (tmp_path / "target.dfn").write_text(
        (
            "define the potential position<my.domain.com:my_lib:/target> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</leaf>.\n"
            "    }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "leaf.dfn").write_text(
        "define the potential position<my.domain.com:my_lib:/leaf>.\n",
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
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[2].file_path == define_path.DefinePath("leaf.dfn")


@pytest.mark.xfail(
    raises=KeyError,
    strict=True,
    reason=(
        "In non-filesystem mode, no project root is registered with the"
        " path_tracker, so a back-reference to an in-source cross-universe"
        " definition crashes in program_validator._resolve_target_file when"
        " path_tracker.has_sub_root looks up the empty parent root in"
        " self._project_roots and raises KeyError."
    ),
)
def test_non_filesystem_cross_universe_back_reference():
    foreign_universe = "demo_mv:demo.example:demo_universe"
    source = (
        f"define the potential position<{foreign_universe}:/target>.\n"
        f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{foreign_universe}:/target>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert result.all_exceptions == []
