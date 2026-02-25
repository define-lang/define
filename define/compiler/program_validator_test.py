# pyright: reportUnusedCallResult=false
"""Tests for ProgramValidator parallel coordinator."""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions, program_validator
from define.compiler.program_validator_tests import test_helpers

_POSITION_WITH_REF = (
    "define the potential position<my.domain.com:my_lib:/{name}> {{\n"
    "it may only contain dimension points where {{\n"
    "it has the position</{ref}>.\n"
    "}}\n"
    "}}\n"
)


def _write_def(tmp_path: Path, name: str, content: str):
    (tmp_path / f"{name}.def").write_text(content, encoding="utf-8")


def _simple_position(name: str) -> str:
    return f"define the potential position<my.domain.com:my_lib:/{name}>.\n"


def _position_with_ref(name: str, ref: str) -> str:
    return _POSITION_WITH_REF.format(name=name, ref=ref)


def _position_with_refs(name: str, refs: list[str]) -> str:
    ref_lines = "".join(f"it has the position</{r}>.\n" for r in refs)
    return (
        f"define the potential position<my.domain.com:my_lib:/{name}> {{\n"
        f"it may only contain dimension points where {{\n"
        f"{ref_lines}"
        f"}}\n"
        f"}}\n"
    )


class TestSingleFile:
    def test_valid_position(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _simple_position("test"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        assert len(results) == 1
        assert results[0].exception is None
        assert results[0].diagnostics == []

    def test_file_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("nonexistent.def")
        )
        assert len(results) == 1
        assert isinstance(results[0].exception, exceptions.SourceFileNotFoundError)


class TestMultiFile:
    def test_reference_to_existing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _position_with_ref("test", "other"))
        _write_def(tmp_path, "other", _simple_position("other"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        assert len(results) == 2
        assert all(r.exception is None for r in results)
        assert all(r.diagnostics == [] for r in results)

    def test_reference_to_missing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _position_with_ref("test", "missing"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        assert len(results) == 1
        test_result = results[0]
        assert [type(d) for d in test_result.diagnostics] == [
            diagnostics.ReferencedFileNotFoundDiagnostic,
        ]

    def test_reference_wrong_type(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _position_with_ref("test", "other"))
        _write_def(
            tmp_path,
            "other",
            "define the potential action<my.domain.com:my_lib:/other>.\n",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diag_types = [type(d) for r in results for d in r.diagnostics]
        assert all_diag_types == [
            diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
        ]

    def test_wrong_type_detected_without_deferral(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Covers the non-deferred branch in _process_reference_edges,
        # where the target file's result is already available when the
        # source file's edges are processed.
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        # root → hub, hub discovers target then checker (in that order).
        # With max_workers=1 (FIFO), target completes before checker.
        # When checker's edges are processed, target's result is already
        # stored, so checker→target validates without deferral.
        _write_def(tmp_path, "root", _position_with_ref("root", "hub"))
        _write_def(tmp_path, "hub", _position_with_refs("hub", ["target", "checker"]))
        _write_def(
            tmp_path,
            "target",
            "define the potential action<my.domain.com:my_lib:/target>.\n",
        )
        _write_def(tmp_path, "checker", _position_with_ref("checker", "target"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("root.def"), max_workers=1
        )
        checker_result = next(
            r for r in results if r.file_path == PurePosixPath("checker.def")
        )
        assert [type(d) for d in checker_result.diagnostics] == [
            diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
        ]


class TestCrossFileDuplicate:
    def test_duplicate_does_not_corrupt_reference_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "root", _position_with_refs("root", ["target", "dup"]))
        _write_def(tmp_path, "target", _simple_position("target"))
        _write_def(
            tmp_path,
            "dup",
            (
                "define the potential position<my.domain.com:my_lib:/target>.\n"
                "define the potential position<my.domain.com:my_lib:/dup>.\n"
            ),
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("root.def"), max_workers=1
        )
        all_diag_types = [type(d) for r in results for d in r.diagnostics]
        assert all_diag_types == [
            diagnostics.PathMismatchDiagnostic,
        ]
        root_result = next(
            r for r in results if r.file_path == PurePosixPath("root.def")
        )
        assert root_result.diagnostics == []


class TestDuplicateFqun:
    def test_sub_root_redeclares_parent_fqun(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        parent_fqun = "mv:define-lang.org:parent"
        child_fqun = "mv:define-lang.org:child"
        test_helpers.write_project_config(tmp_path, parent_fqun)
        test_helpers.write_local_deps_config(tmp_path, {child_fqun: "lib"})
        test_helpers.write_sub_root(tmp_path, "lib", child_fqun)
        test_helpers.write_local_deps_config(tmp_path / "lib", {parent_fqun: "nested"})
        test_helpers.write_sub_root(tmp_path, "lib/nested", parent_fqun)
        _write_def(
            tmp_path,
            "test",
            f"define the potential position<{parent_fqun}:/test> {{\n"
            + "it may only contain dimension points where {\n"
            + f"it has the position<{child_fqun}:/target>.\n"
            + "}\n"
            + "}\n",
        )
        _write_def(
            tmp_path / "lib",
            "target",
            f"define the potential position<{child_fqun}:/target> {{\n"
            + "it may only contain dimension points where {\n"
            + f"it has the position<{parent_fqun}:/leaf>.\n"
            + "}\n"
            + "}\n",
        )
        (tmp_path / "lib" / "nested" / "leaf.def").write_text(
            f"define the potential position<{parent_fqun}:/leaf>.\n",
            encoding="utf-8",
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
        assert diag.position.column == 21
        assert isinstance(diag.error, exceptions.DuplicateFqunError)
        assert diag.error.fqun == parent_fqun
        assert diag.error.existing_config == PurePosixPath(
            ".define/project/config.defcl"
        )
        assert diag.error.new_config == PurePosixPath(
            "lib/nested/.define/project/config.defcl"
        )


class TestCycleDetection:
    def test_self_cycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _position_with_ref("test", "test"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diag_types = [type(d) for r in results for d in r.diagnostics]
        assert all_diag_types == [
            diagnostics.CircularGlobalReferenceDiagnostic,
        ]

    def test_two_node_cycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "alpha", _position_with_ref("alpha", "beta"))
        _write_def(tmp_path, "beta", _position_with_ref("beta", "alpha"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("alpha.def")
        )
        all_diag_types = [type(d) for r in results for d in r.diagnostics]
        assert all_diag_types == [
            diagnostics.CircularGlobalReferenceDiagnostic,
        ]


class TestEncounterOrder:
    def test_results_in_encounter_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "test", _position_with_ref("test", "other"))
        _write_def(tmp_path, "other", _simple_position("other"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        assert len(results) == 2
        assert results[0].file_path == PurePosixPath("test.def")
        assert results[1].file_path == PurePosixPath("other.def")


class TestConfigErrors:
    def test_no_project_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        assert len(results) == 1
        assert isinstance(results[0].exception, exceptions.ConfigError)


class TestParallelExecution:
    def test_fan_out(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        leaf_names = [f"leaf_{i}" for i in range(10)]
        _write_def(tmp_path, "root", _position_with_refs("root", leaf_names))
        for name in leaf_names:
            _write_def(tmp_path, name, _simple_position(name))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("root.def"), max_workers=4
        )
        assert len(results) == 11
        assert all(r.exception is None for r in results)
        assert all(r.diagnostics == [] for r in results)

    def test_deep_chain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        chain = ["a", "b", "c", "d", "e"]
        for i, name in enumerate(chain[:-1]):
            _write_def(tmp_path, name, _position_with_ref(name, chain[i + 1]))
        _write_def(tmp_path, chain[-1], _simple_position(chain[-1]))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("a.def"), max_workers=4
        )
        assert len(results) == 5
        assert all(r.exception is None for r in results)
        assert all(r.diagnostics == [] for r in results)

    def test_diamond_dependency(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        _write_def(tmp_path, "top", _position_with_refs("top", ["left", "right"]))
        _write_def(tmp_path, "left", _position_with_ref("left", "bottom"))
        _write_def(tmp_path, "right", _position_with_ref("right", "bottom"))
        _write_def(tmp_path, "bottom", _simple_position("bottom"))
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("top.def"), max_workers=4
        )
        assert len(results) == 4
        assert all(r.exception is None for r in results)
        assert all(r.diagnostics == [] for r in results)
