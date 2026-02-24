# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions, validator
from define.compiler.validator_tests import test_helpers
from define.compiler.validator_tests.conftest import ParseAndValidateFile


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

    results = validator.Validator().parse_and_validate_program(
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
            + "it may only contain dimension points where {\n"
            + "it has the position</middle>.\n"
            + "}\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "middle.def",
        (
            "define the potential position<mv:define-lang.org:walk_order:/middle> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</leaf>.\n"
            + "}\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "leaf.def",
        "define the potential position<mv:define-lang.org:walk_order:/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert [result.file_path for result in results] == [
        PurePosixPath("test.def"),
        PurePosixPath("middle.def"),
        PurePosixPath("leaf.def"),
    ]


def test_self_cycle_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</test>.\n"
        "}\n"
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
    assert diags[0].position.column == 21
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
            + "it may only contain dimension points where {\n"
            + "it has the position</loop>.\n"
            + "}\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "loop.def").write_text(
        (
            "define the potential position<mv:define-lang.org:test_walk_cycle:/loop> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</test>.\n"
            + "}\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    test_helpers.write_project_config(tmp_path, "mv:define-lang.org:test_walk_cycle")
    monkeypatch.chdir(tmp_path)
    results = validator.Validator().parse_and_validate_program(
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
    assert diags[0].position.column == 21
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<mv:define-lang.org:test_walk_cycle:/test>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/loop>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/test>"
    )


_EXTERNAL_UNIVERSE_SOURCE = (
    "define the potential position<my.domain.com:my_lib:/test> {\n"
    "it may only contain dimension points where {\n"
    "it has the position<other.example.com:other_universe:/target>.\n"
    "}\n"
    "}\n"
)


def test_external_universe_no_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    diags = test_helpers.parse_transform_validate(_EXTERNAL_UNIVERSE_SOURCE)
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].config_path == ".define/project/config.defcl"


def test_external_universe_without_local_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    diags = test_helpers.parse_transform_validate(_EXTERNAL_UNIVERSE_SOURCE)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
    diags = test_helpers.parse_transform_validate(_EXTERNAL_UNIVERSE_SOURCE)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
    diags = test_helpers.parse_transform_validate(_EXTERNAL_UNIVERSE_SOURCE)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
    diags = test_helpers.parse_transform_validate(_EXTERNAL_UNIVERSE_SOURCE)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)


def test_unknown_universe_emits_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "it may only contain dimension points where {\n"
        "it has the position<other.example.com:other_universe:/target>.\n"
        "}\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_duplicate_unknown_universe_emits_one_diagnostic(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "it may only contain dimension points where {\n"
        "it has the position<other.example.com:other_universe:/target>.\n"
        "it has the position<other.example.com:other_universe:/another>.\n"
        "}\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    diags = result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
            "it may only contain dimension points where {\n"
            "it has the position<other.example.com:other_universe:/target>.\n"
            "it has the position</other>.\n"
            "}\n"
            "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "other.def",
        (
            "define the potential position<my.domain.com:my_lib:/other> {\n"
            "it may only contain dimension points where {\n"
            "it has the position<other.example.com:other_universe:/another>.\n"
            "}\n"
            "}\n"
        ),
    )
    monkeypatch.chdir(tmp_path)

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 2
    for diag in all_diags:
        assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
        assert diag.position.line == 3
        assert diag.position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/target>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/missing>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"it has the position</other>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "other.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/other> {{\n"
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/another>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert all_diags[0].position.line == 3
    assert all_diags[0].position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{wrong_universe}:/target>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)
    assert diags[0].error.expected_fqun == _CHILD_UNIVERSE
    assert diags[0].error.actual_fqun == wrong_universe


def test_sub_root_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _setup_cross_fqun_project(tmp_path, monkeypatch)
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD_UNIVERSE)
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"it may only contain dimension points where {{\n"
            f"it has the position</lib/parent_target>.\n"
            f"it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
            f"}}\n"
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

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert [type(d) for d in results[0].diagnostics] == [
        diagnostics.SubRootAlreadyOccupiedDiagnostic,
        diagnostics.PathInsideOtherUniverseDiagnostic,
    ]
    sub_root_diag = results[0].diagnostics[0]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position</lib/parent_target>.\n"
            f"it has the position<{_CHILD_UNIVERSE}:/missing_target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/parent_target.def",
        f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 2
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[0].exception is None
    assert [type(d) for d in results[0].diagnostics] == [
        diagnostics.SubRootAlreadyOccupiedDiagnostic,
        diagnostics.PathInsideOtherUniverseDiagnostic,
        diagnostics.ReferencedFileNotFoundDiagnostic,
    ]
    sub_root_diag = results[0].diagnostics[0]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 21
    assert sub_root_diag.universe == _CHILD_UNIVERSE
    assert sub_root_diag.sub_root_path == "lib"
    assert sub_root_diag.existing_file == "lib/parent_target.def"
    assert sub_root_diag.existing_universe == _PARENT_UNIVERSE
    not_found_diag = results[0].diagnostics[2]
    assert isinstance(not_found_diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert not_found_diag.position.line == 4
    assert not_found_diag.position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
            f"it has the position</lib/parent_target>.\n"
            f"}}\n"
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

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    path_diags = [
        d
        for d in all_diags
        if isinstance(d, diagnostics.PathInsideOtherUniverseDiagnostic)
    ]
    assert len(path_diags) == 1
    assert path_diags[0].position.line == 4
    assert path_diags[0].position.column == 21
    assert path_diags[0].other_universe == _CHILD_UNIVERSE
    assert path_diags[0].path.endswith("lib/parent_target.def")
    assert path_diags[0].sub_root_path == "lib"


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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    wrong_fqun = "mv:define-lang.org:totally_wrong"
    _write_source(
        tmp_path,
        "lib/target.def",
        f"define the potential position<{wrong_fqun}:/target>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
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
    assert results[0].diagnostics[0].position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        (
            f"define the potential action<{_CHILD_UNIVERSE}:/target> {{\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"}}\n"
            f"}}\n"
        ),
    )

    results = validator.Validator().parse_and_validate_program(
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
    assert results[0].diagnostics[0].position.column == 21
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/entry>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/entry.def",
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/entry> {{\n"
            f"it may only contain dimension points where {{\n"
            f"it has the position</leaf>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/leaf.def",
        f"define the potential position<{_CHILD_UNIVERSE}:/leaf>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
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
            f"it may only contain dimension points where {{\n"
            f"it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/target.def",
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/target> {{\n"
            f"it may only contain dimension points where {{\n"
            f"it has the position<{grandchild_universe}:/leaf>.\n"
            f"}}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/inner/leaf.def",
        f"define the potential position<{grandchild_universe}:/leaf>.\n",
    )

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 3
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)
    assert results[0].file_path == PurePosixPath("test.def")
    assert results[1].file_path == PurePosixPath("lib/target.def")
    assert results[2].file_path == PurePosixPath("lib/inner/leaf.def")
