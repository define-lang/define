# pyright: reportUnusedCallResult=false
"""Cross-FQUN global name walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.conftest import ValidateProject
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

_PARENT_UNIVERSE = "mv:define-lang.org:parent_universe"
_CHILD_UNIVERSE = "mv:define-lang.org:child_universe"


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
    (tmp_path / "test.def").write_text(
        (
            f"define the potential position<{parent_fqun}:/test> {{\n"
            + "    it may only contain dimension points where {\n"
            + f"        it has the position<{child_fqun}:/target>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib/target.def").write_text(
        (
            f"define the potential position<{child_fqun}:/target> {{\n"
            + "    it may only contain dimension points where {\n"
            + f"        it has the position<{parent_fqun}:/leaf>.\n"
            + "    }\n"
            + "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib/nested/leaf.def").write_text(
        f"define the potential position<{parent_fqun}:/leaf>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = program_validator.ProgramStructuralValidator().validate_program(
        PurePosixPath("test.def"), max_workers=1
    )
    all_diags = result.all_diagnostics
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


def test_cross_fqun_walks_into_sub_root(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/target.def": f"define the potential position<{_CHILD_UNIVERSE}:/target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 2
    assert not result.has_errors()
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")


def test_cross_fqun_file_not_found(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/missing>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 1
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[0].file_path == "lib/missing.def"


def test_cross_fqun_sub_root_missing_config(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
    )
    assert len(result.file_results) == 1
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)


def test_cross_fqun_sub_root_missing_config_across_files_emits_one_diagnostic(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"        it has the position</other>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "other.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/other> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/another>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert all_diags[0].position.line == 3
    assert all_diags[0].position.column == 29
    assert isinstance(all_diags[0].error, exceptions.NotProjectRootError)


def test_cross_fqun_sub_root_fqun_mismatch(validate_project: ValidateProject):
    wrong_universe = "mv:define-lang.org:wrong_universe"
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/target.def": f"define the potential position<{wrong_universe}:/target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": wrong_universe},
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)
    assert diags[0].error.expected_fqun == _CHILD_UNIVERSE
    assert diags[0].error.actual_fqun == wrong_universe
    assert diags[0].error.sub_root_path == "lib"


def test_already_loaded_root_fqun_mismatch(validate_project: ValidateProject):
    second_child = "mv:define-lang.org:second_child"
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"        it has the position<{second_child}:/other>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/target.def": f"define the potential position<{_CHILD_UNIVERSE}:/target>.\n",
            "lib/other.def": f"define the potential position<{_CHILD_UNIVERSE}:/other>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib", second_child: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
        max_workers=1,
    )
    assert len(result.file_results) == 2
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 4
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.SubRootFqunMismatchError)
    assert diags[0].error.expected_fqun == second_child
    assert diags[0].error.actual_fqun == _CHILD_UNIVERSE
    assert diags[0].error.sub_root_path == "lib"
    assert result.file_results[1].diagnostics == []


def test_sub_root_conflict(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</lib/parent_target>.\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/parent_target.def": f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
            "lib/sub_root_target.def": f"define the potential position<{_CHILD_UNIVERSE}:/sub_root_target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 3
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 2
    path_diag = result.file_results[0].diagnostics[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.position.line == 3
    assert path_diag.position.column == 29
    assert path_diag.path.endswith("lib/parent_target.def")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    sub_root_diag = result.file_results[0].diagnostics[1]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 29
    assert sub_root_diag.universe == _CHILD_UNIVERSE
    assert sub_root_diag.sub_root_path == "lib"
    assert sub_root_diag.existing_file == "lib/parent_target.def"
    assert sub_root_diag.existing_universe == _PARENT_UNIVERSE
    assert result.file_results[1].file_path == PurePosixPath("lib/parent_target.def")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == PurePosixPath("lib/sub_root_target.def")
    assert result.file_results[2].exception is None
    assert result.file_results[2].diagnostics == []


def test_sub_root_conflict_continues_validation(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</lib/parent_target>.\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/missing_target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/parent_target.def": f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 3
    path_diag = result.file_results[0].diagnostics[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.position.line == 3
    assert path_diag.position.column == 29
    assert path_diag.path.endswith("lib/parent_target.def")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    sub_root_diag = result.file_results[0].diagnostics[2]
    assert isinstance(sub_root_diag, diagnostics.SubRootAlreadyOccupiedDiagnostic)
    assert sub_root_diag.position.line == 4
    assert sub_root_diag.position.column == 29
    assert sub_root_diag.universe == _CHILD_UNIVERSE
    assert sub_root_diag.sub_root_path == "lib"
    assert sub_root_diag.existing_file == "lib/parent_target.def"
    assert sub_root_diag.existing_universe == _PARENT_UNIVERSE
    not_found_diag = result.file_results[0].diagnostics[1]
    assert isinstance(not_found_diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert not_found_diag.position.line == 4
    assert not_found_diag.position.column == 29
    assert not_found_diag.file_path == "lib/missing_target.def"
    assert result.file_results[1].file_path == PurePosixPath("lib/parent_target.def")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_path_inside_other_universe(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/sub_root_target>.\n"
                f"        it has the position</lib/parent_target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/sub_root_target.def": f"define the potential position<{_CHILD_UNIVERSE}:/sub_root_target>.\n",
            "lib/parent_target.def": f"define the potential position<{_PARENT_UNIVERSE}:/lib/parent_target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 3
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.PathInsideOtherUniverseDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].position.line == 4
    assert result.file_results[0].diagnostics[0].position.column == 29
    assert result.file_results[0].diagnostics[0].path.endswith("lib/parent_target.def")
    assert result.file_results[0].diagnostics[0].other_universe == _CHILD_UNIVERSE
    assert result.file_results[0].diagnostics[0].sub_root_path == "lib"
    assert result.file_results[1].file_path == PurePosixPath("lib/sub_root_target.def")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == PurePosixPath("lib/parent_target.def")
    assert result.file_results[2].exception is None
    assert result.file_results[2].diagnostics == []


def test_path_inside_other_universe_skips_further_validation(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/child_action>.\n"
                f"        it has the position</lib/child_action>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/child_action.def": (
                f"define the potential action<{_CHILD_UNIVERSE}:/child_action> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<_noop>.\n"
                f"        create a dimension point in position<_noop>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 2
    wrong_type_diag = result.file_results[0].diagnostics[0]
    assert isinstance(
        wrong_type_diag, diagnostics.ReferencedGlobalNameWrongTypeDiagnostic
    )
    assert wrong_type_diag.position.line == 3
    assert wrong_type_diag.position.column == 29
    assert wrong_type_diag.path == "/child_action"
    assert wrong_type_diag.expected_type == "position"
    path_diag = result.file_results[0].diagnostics[1]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.position.line == 4
    assert path_diag.position.column == 29
    assert path_diag.path.endswith("lib/child_action.def")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    assert result.file_results[1].file_path == PurePosixPath("lib/child_action.def")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_cross_fqun_file_wrong_fqun_in_sub_root(validate_project: ValidateProject):
    wrong_fqun = "mv:define-lang.org:totally_wrong"
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/target.def": f"define the potential position<{wrong_fqun}:/target>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].position.line == 3
    assert result.file_results[0].diagnostics[0].position.column == 29
    assert result.file_results[0].diagnostics[0].path == "/target"
    assert result.file_results[0].diagnostics[0].expected_type == "position"
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0], diagnostics.FqunMismatchDiagnostic
    )
    assert result.file_results[1].diagnostics[0].position.line == 1
    assert result.file_results[1].diagnostics[0].position.column == 31
    assert result.file_results[1].diagnostics[0].expected == _CHILD_UNIVERSE
    assert result.file_results[1].diagnostics[0].actual == wrong_fqun


def test_cross_fqun_wrong_type_in_sub_root(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/target.def": (
                f"define the potential action<{_CHILD_UNIVERSE}:/target> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<_noop>.\n"
                f"        create a dimension point in position<_noop>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].position.line == 3
    assert result.file_results[0].diagnostics[0].position.column == 29
    assert result.file_results[0].diagnostics[0].path == "/target"
    assert result.file_results[0].diagnostics[0].expected_type == "position"
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_same_fqun_reference_inside_sub_root(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/entry>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/entry.def": (
                f"define the potential position<{_CHILD_UNIVERSE}:/entry> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</leaf>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/leaf.def": f"define the potential position<{_CHILD_UNIVERSE}:/leaf>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
        sub_roots={"lib": _CHILD_UNIVERSE},
    )
    assert len(result.file_results) == 3
    assert not result.has_errors()
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[1].file_path == PurePosixPath("lib/entry.def")
    assert result.file_results[2].file_path == PurePosixPath("lib/leaf.def")


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

    (tmp_path / "test.def").write_text(
        (
            f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
            f"    }}\n"
            f"}}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib/target.def").write_text(
        (
            f"define the potential position<{_CHILD_UNIVERSE}:/target> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position<{grandchild_universe}:/leaf>.\n"
            f"    }}\n"
            f"}}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "lib/inner/leaf.def").write_text(
        f"define the potential position<{grandchild_universe}:/leaf>.\n",
        encoding="utf-8",
    )

    result = program_validator.ProgramStructuralValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(result.file_results) == 3
    assert not result.has_errors()
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")
    assert result.file_results[2].file_path == PurePosixPath("lib/inner/leaf.def")


def test_failed_root_discovery_does_not_skip_remaining_files(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target_a>.\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target_b>.\n"
                f"        it has the position</local>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "local.def": f"define the potential position<{_PARENT_UNIVERSE}:/local>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert isinstance(diags[0].error, exceptions.NotProjectRootError)
    assert result.file_results[1].file_path == PurePosixPath("local.def")
    assert result.file_results[1].diagnostics == []


def test_failed_root_edge_does_not_skip_remaining_edge_validation(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.def": (
                f"define the potential position<{_PARENT_UNIVERSE}:/test> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position<{_CHILD_UNIVERSE}:/target>.\n"
                f"        it has the position</wrong_type>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "wrong_type.def": f"define the potential action<{_PARENT_UNIVERSE}:/wrong_type>.\n",
        },
        universe_name=_PARENT_UNIVERSE,
        local_deps={_CHILD_UNIVERSE: "lib"},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diags[0].path == "/wrong_type"
    assert diags[0].expected_type == "position"
    assert diags[0].position.line == 4
    assert diags[0].position.column == 29
    assert isinstance(diags[1], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[1].position.line == 3
    assert diags[1].position.column == 29
    assert isinstance(diags[1].error, exceptions.NotProjectRootError)
    assert result.file_results[1].file_path == PurePosixPath("wrong_type.def")
    assert result.file_results[1].diagnostics == []
