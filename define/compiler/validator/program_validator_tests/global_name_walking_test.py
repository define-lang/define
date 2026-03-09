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
)


def _write_source(tmp_path: Path, rel_path: str, source: str) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_nested_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "test.example.com:my_lib")
    _write_source(
        tmp_path,
        "sub/dir/leaf.def",
        "define the potential position<test.example.com:my_lib:/sub/dir/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("sub/dir/leaf.def")
    )
    assert len(results) == 1
    result = results[0]
    assert result.exception is None
    assert result.diagnostics == []
    assert result.file_path == PurePosixPath("sub/dir/leaf.def")


def test_walk_returns_results_in_encounter_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "mv:define-lang.org:walk_order")
    _write_source(
        tmp_path,
        "test.def",
        (
            "define the potential position<mv:define-lang.org:walk_order:/test> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</middle>.\n"
            + "    }\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "middle.def",
        (
            "define the potential position<mv:define-lang.org:walk_order:/middle> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</leaf>.\n"
            + "    }\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "leaf.def",
        "define the potential position<mv:define-lang.org:walk_order:/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert [result.file_path for result in results] == [
        PurePosixPath("test.def"),
        PurePosixPath("middle.def"),
        PurePosixPath("leaf.def"),
    ]


def test_duplicate_does_not_corrupt_reference_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_source(
        tmp_path,
        "root.def",
        (
            "define the potential position<my.domain.com:my_lib:/root> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</target>.\n"
            "        it has the position</dup>.\n"
            "    }\n"
            "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "target.def",
        "define the potential position<my.domain.com:my_lib:/target>.\n",
    )
    _write_source(
        tmp_path,
        "dup.def",
        (
            "define the potential position<my.domain.com:my_lib:/target>.\n"
            "define the potential position<my.domain.com:my_lib:/dup>.\n"
        ),
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("root.def"), max_workers=1
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_source(
        tmp_path,
        "test.def",
        (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "other.def",
        (
            "define the potential position<my.domain.com:my_lib:/other> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</test>.\n"
            "    }\n"
            "}\n"
        ),
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
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


def test_two_file_cycle_emits_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "test.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_cycle:/test> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</loop>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "loop.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_cycle:/loop> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position</test>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    test_helpers.write_project_config(tmp_path, "mv:define-lang.org:test_walk_cycle")
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        _EXTERNAL_UNIVERSE_SOURCE
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        _EXTERNAL_UNIVERSE_SOURCE
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        _EXTERNAL_UNIVERSE_SOURCE
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        _EXTERNAL_UNIVERSE_SOURCE
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
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        _EXTERNAL_UNIVERSE_SOURCE
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_source(
        tmp_path,
        "test.def",
        (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position<other.example.com:other_universe:/target>.\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "other.def",
        (
            "define the potential position<my.domain.com:my_lib:/other> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position<other.example.com:other_universe:/another>.\n"
            "    }\n"
            "}\n"
        ),
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 2
    for diag in all_diags:
        assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
        assert diag.position.line == 3
        assert diag.position.column == 29
        assert diag.universe == "other.example.com:other_universe"
        assert diag.current_universe_name == "my.domain.com:my_lib"


_PARENT_UNIVERSE = "mv:define-lang.org:parent_universe"
_CHILD_UNIVERSE = "mv:define-lang.org:child_universe"


def _setup_cross_fqun_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_universe: str = _CHILD_UNIVERSE,
    sub_root_path: str = "lib",
) -> None:
    test_helpers.write_project_config(tmp_path, _PARENT_UNIVERSE)
    test_helpers.write_local_deps_config(tmp_path, {child_universe: sub_root_path})
    monkeypatch.chdir(tmp_path)


def test_sub_root_redeclares_parent_fqun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    parent_fqun = "mv:define-lang.org:parent"
    child_fqun = "mv:define-lang.org:child"
    test_helpers.write_project_config(tmp_path, parent_fqun)
    test_helpers.write_local_deps_config(tmp_path, {child_fqun: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_fqun)
    test_helpers.write_local_deps_config(tmp_path / "lib", {parent_fqun: "nested"})
    test_helpers.write_sub_root(tmp_path, "lib/nested", parent_fqun)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{parent_fqun}:/test> {{\n"
            + "    it may only contain dimension points where {\n"
            + f"        it has the position<{child_fqun}:/target>.\n"
            + "    }\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        (
            f"define the potential position<{child_fqun}:/target> {{\n"
            + "    it may only contain dimension points where {\n"
            + f"        it has the position<{parent_fqun}:/leaf>.\n"
            + "    }\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/nested/leaf.def",
        f"define the potential position<{parent_fqun}:/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def"), max_workers=1
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.ConfigLoadErrorDiagnostic)
    assert diag.position.line == 3
    assert diag.position.column == 29
    assert isinstance(diag.error, exceptions.DuplicateFqunError)
    assert diag.error.fqun == parent_fqun
    assert diag.error.existing_config == PurePosixPath(".define/project/config.defcl")
    assert diag.error.new_config == PurePosixPath(
        "lib/nested/.define/project/config.defcl"
    )


def test_cross_fqun_walks_into_sub_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[1].file_path == PurePosixPath("lib/target.def")


def test_cross_fqun_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/missing>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[0].file_path == "lib/missing.def"


def test_cross_fqun_sub_root_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    (tmp_path / "lib").mkdir(parents=True, exist_ok=True)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)


def test_cross_fqun_sub_root_missing_config_across_files_emits_one_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Verifies that a failed sub-root config is only loaded once,
    # emitting one diagnostic even when multiple files reference it.
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    (tmp_path / "lib").mkdir(parents=True, exist_ok=True)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"        it has the position</other>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "other.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/other> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/another>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert all_diags[0].position.line == 3
    assert all_diags[0].position.column == 29
    assert isinstance(all_diags[0].error, exceptions.NotProjectRootError)


def test_cross_fqun_sub_root_fqun_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    wrong_universe = "mv:define-lang.org:wrong_universe"
    test_helpers.write_sub_root(tmp_path, "lib", wrong_universe)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{wrong_universe}:/target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)
    assert diags[0].error.expected_fqun == _CHILD_UNIVERSE
    assert diags[0].error.actual_fqun == wrong_universe
    assert diags[0].error.sub_root_path == "lib"


# Covers the "already loaded root" mismatch path in _do_load_root_config,
# where a root was successfully loaded by a prior reference and a second
# reference tries to load the same root with a different expected fqun.
# (test_cross_fqun_sub_root_fqun_mismatch above covers the "fresh load" path.)
def test_already_loaded_root_fqun_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    second_child = "mv:define-lang.org:second_child"
    test_helpers.write_project_config(tmp_path, _PARENT_UNIVERSE)
    test_helpers.write_local_deps_config(
        tmp_path, {_CHILD_UNIVERSE: "lib", second_child: "lib"}
    )
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"        it has the position<{second_child}:/other>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/target>.\n",
    )
    _write_source(
        tmp_path,
        "lib/other.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/other>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def"), max_workers=1
    )
    assert len(results) == 2
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)
    assert diags[0].error.expected_fqun == second_child
    assert diags[0].error.actual_fqun == _CHILD_UNIVERSE
    assert diags[0].error.sub_root_path == "lib"
    assert results[1].diagnostics == []


def test_sub_root_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</lib/parent_target>.\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/parent_target.def",
        f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
    )
    _write_source(
        tmp_path,
        "lib/sub_root_target.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/sub_root_target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert len(results[0].diagnostics) == 2
    path_diag = results[0].diagnostics[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.position.line == 3
    assert path_diag.position.column == 29
    assert path_diag.path.endswith("lib/parent_target.def")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    sub_root_diag = results[0].diagnostics[1]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 29
    assert sub_root_diag.universe == _CHILD_UNIVERSE
    assert sub_root_diag.sub_root_path == "lib"
    assert sub_root_diag.existing_file == "lib/parent_target.def"
    assert sub_root_diag.existing_universe == _PARENT_UNIVERSE
    assert results[1].file_path == PurePosixPath("lib/parent_target.def")
    assert results[1].exception is None
    assert results[1].diagnostics == []
    assert results[2].file_path == PurePosixPath("lib/sub_root_target.def")
    assert results[2].exception is None
    assert results[2].diagnostics == []


def test_sub_root_conflict_continues_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</lib/parent_target>.\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/missing_target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/parent_target.def",
        f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert len(results[0].diagnostics) == 3
    path_diag = results[0].diagnostics[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.position.line == 3
    assert path_diag.position.column == 29
    assert path_diag.path.endswith("lib/parent_target.def")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    sub_root_diag = results[0].diagnostics[2]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 29
    assert sub_root_diag.universe == _CHILD_UNIVERSE
    assert sub_root_diag.sub_root_path == "lib"
    assert sub_root_diag.existing_file == "lib/parent_target.def"
    assert sub_root_diag.existing_universe == _PARENT_UNIVERSE
    not_found_diag = results[0].diagnostics[1]
    assert isinstance(not_found_diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert not_found_diag.position.line == 4
    assert not_found_diag.position.column == 29
    assert not_found_diag.file_path == "lib/missing_target.def"
    assert results[1].file_path == PurePosixPath("lib/parent_target.def")
    assert results[1].exception is None
    assert results[1].diagnostics == []


def test_path_inside_other_universe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
            f"        it has the position</lib/parent_target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/sub_root_target.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/sub_root_target>.\n",
    )
    _write_source(
        tmp_path,
        "lib/parent_target.def",
        f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert len(results[0].diagnostics) == 1
    assert isinstance(
        results[0].diagnostics[0], diagnostics.PathInsideOtherUniverseDiagnostic
    )
    assert results[0].diagnostics[0].position.line == 4
    assert results[0].diagnostics[0].position.column == 29
    assert results[0].diagnostics[0].path.endswith("lib/parent_target.def")
    assert results[0].diagnostics[0].other_universe == _CHILD_UNIVERSE
    assert results[0].diagnostics[0].sub_root_path == "lib"
    assert results[1].file_path == PurePosixPath("lib/sub_root_target.def")
    assert results[1].exception is None
    assert results[1].diagnostics == []
    assert results[2].file_path == PurePosixPath("lib/parent_target.def")
    assert results[2].exception is None
    assert results[2].diagnostics == []


def test_cross_fqun_file_wrong_fqun_in_sub_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    wrong_fqun = "mv:define-lang.org:totally_wrong"
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{wrong_fqun}:/target>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert len(results[0].diagnostics) == 1
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    )
    assert results[0].diagnostics[0].position.line == 3
    assert results[0].diagnostics[0].position.column == 29
    assert results[0].diagnostics[0].path == "/target"
    assert results[0].diagnostics[0].expected_type == "position"
    assert results[1].file_path == PurePosixPath("lib/target.def")
    assert results[1].exception is None
    assert len(results[1].diagnostics) == 1
    assert isinstance(results[1].diagnostics[0], diagnostics.FqunMismatchDiagnostic)
    assert results[1].diagnostics[0].position.line == 1
    assert results[1].diagnostics[0].position.column == 31
    assert results[1].diagnostics[0].expected == _CHILD_UNIVERSE
    assert results[1].diagnostics[0].actual == wrong_fqun


def test_cross_fqun_wrong_type_in_sub_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        (
            f"define the potential action<{_CHILD_UNIVERSE}:/target> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"    }}\n"
            f"}}\n"
        ),
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert len(results[0].diagnostics) == 1
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    )
    assert results[0].diagnostics[0].position.line == 3
    assert results[0].diagnostics[0].position.column == 29
    assert results[0].diagnostics[0].path == "/target"
    assert results[0].diagnostics[0].expected_type == "position"
    assert results[1].file_path == PurePosixPath("lib/target.def")
    assert results[1].exception is None
    assert results[1].diagnostics == []


def test_same_fqun_reference_inside_sub_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/entry>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/entry.def",
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/entry> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</leaf>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/leaf.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/leaf>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[1].file_path == PurePosixPath("lib/entry.def")
    assert results[2].file_path == PurePosixPath("lib/leaf.def")


def test_cross_fqun_nested_sub_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    grandchild_universe = "mv:define-lang.org:grandchild_universe"
    test_helpers.write_project_config(tmp_path, _PARENT_UNIVERSE)
    test_helpers.write_local_deps_config(tmp_path, {_CHILD_UNIVERSE: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    test_helpers.write_local_deps_config(
        tmp_path / "lib", {grandchild_universe: "inner"}
    )
    test_helpers.write_sub_root(tmp_path, "lib/inner", grandchild_universe)
    monkeypatch.chdir(tmp_path)

    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/target> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{grandchild_universe}:/leaf>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/inner/leaf.def",
        f"define the potential position<{grandchild_universe}:/leaf>.\n",
    )

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[1].file_path == PurePosixPath("lib/target.def")
    assert results[2].file_path == PurePosixPath("lib/inner/leaf.def")
