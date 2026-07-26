# pyright: reportUnusedCallResult=false
"""Tests for driver-only behavior."""

from pathlib import Path, PureWindowsPath

import pytest

from define.compiler import (
    diagnostics,
    driver,
    exceptions,
    parser,
)
from define.compiler.data_structures import define_path
from define.compiler.validator.test_helpers import assert_no_errors

_PARSER = parser.Parser()


def _setup_project(tmp_path: Path, universe_name: str) -> None:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.defcl"
    config_file.write_text(f'project: {{\n  universe_name: "{universe_name}"\n}}\n')


def _write_source(tmp_path: Path, rel_path: str, source: str) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


class TestPathFormats:
    def test_windows_style_string_path_still_validates_with_posix_file_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "my.domain.com:my_lib")
        source = "define the potential position<my.domain.com:my_lib:/sub/test>.\n"
        _write_source(tmp_path, "sub/test.dfn", source)
        monkeypatch.chdir(tmp_path)

        d = driver.Driver(_PARSER)
        driver_result = d.validate_program(Path(PureWindowsPath("sub\\test.dfn")))
        assert len(driver_result.result.file_results) == 1
        result = driver_result.result.file_results[0]

        assert_no_errors(driver_result.result)
        assert str(result.file_path) == "sub/test.dfn"


class TestPathResolution:
    def test_absolute_path_is_relativized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        source_file = _write_source(
            tmp_path,
            "hello.dfn",
            "define the potential position<test.example.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver(_PARSER).validate_program(source_file)
        assert len(driver_result.result.file_results) == 1
        assert_no_errors(driver_result.result)
        assert driver_result.result.file_results[0].file_path == define_path.DefinePath(
            "hello.dfn"
        )

    def test_absolute_path_outside_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        _setup_project(project, "test.example.com:my_lib")
        outside = tmp_path / "outside"
        outside.mkdir()
        source_file = outside / "hello.dfn"
        monkeypatch.chdir(project)

        d = driver.Driver(_PARSER)
        with pytest.raises(exceptions.AbsolutePathError) as exc_info:
            d.validate_program(source_file)
        assert exc_info.value.input_path == source_file
        assert exc_info.value.resolved_path == source_file
        assert exc_info.value.project_root == project

    def test_relative_path_with_dotdot_is_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        (tmp_path / "sub").mkdir()
        _write_source(
            tmp_path,
            "hello.dfn",
            "define the potential position<test.example.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver(_PARSER).validate_program(
            Path("sub/../hello.dfn")
        )
        assert len(driver_result.result.file_results) == 1
        assert_no_errors(driver_result.result)
        assert driver_result.result.file_results[0].file_path == define_path.DefinePath(
            "hello.dfn"
        )

    def test_symlink_to_outside_without_dotdot_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        _setup_project(project, "test.example.com:my_lib")
        outside = tmp_path / "outside"
        outside.mkdir()
        _write_source(
            outside,
            "hello.dfn",
            "define the potential position<test.example.com:my_lib:/link/hello>.\n",
        )
        (project / "link").symlink_to(outside)
        monkeypatch.chdir(project)

        driver_result = driver.Driver(_PARSER).validate_program(Path("link/hello.dfn"))
        assert len(driver_result.result.file_results) == 1
        assert_no_errors(driver_result.result)
        assert driver_result.result.file_results[0].file_path == define_path.DefinePath(
            "link/hello.dfn"
        )

    def test_symlink_with_dotdot_escaping_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        _setup_project(project, "test.example.com:my_lib")
        outside = tmp_path / "outside"
        outside.mkdir()
        (project / "link").symlink_to(outside)
        monkeypatch.chdir(project)

        d = driver.Driver(_PARSER)
        with pytest.raises(exceptions.RelativePathError) as exc_info:
            d.validate_program(Path("link/../hello.dfn"))
        assert exc_info.value.input_path == Path("link/../hello.dfn")
        assert exc_info.value.project_root == project.resolve()

    def test_symlink_with_dotdot_staying_in_root_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        (tmp_path / "real" / "sub").mkdir(parents=True)
        _write_source(
            tmp_path,
            "real/hello.dfn",
            "define the potential position<test.example.com:my_lib:/real/hello>.\n",
        )
        (tmp_path / "link").symlink_to(tmp_path / "real" / "sub")
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver(_PARSER).validate_program(
            Path("link/../hello.dfn")
        )
        assert len(driver_result.result.file_results) == 1
        assert_no_errors(driver_result.result)
        assert driver_result.result.file_results[0].file_path == define_path.DefinePath(
            "real/hello.dfn"
        )

    def test_path_escaping_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        monkeypatch.chdir(tmp_path)

        d = driver.Driver(_PARSER)
        with pytest.raises(exceptions.RelativePathError) as exc_info:
            d.validate_program(Path("../hello.dfn"))
        assert exc_info.value.input_path == Path("../hello.dfn")
        assert exc_info.value.project_root == tmp_path.resolve()


class TestSourceValidation:
    def test_clean_source_validates_with_no_errors(self):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        driver_result = driver.Driver(_PARSER).validate_source(source)
        assert len(driver_result.result.file_results) == 1
        assert_no_errors(driver_result.result)
        assert driver_result.result.file_results[0].source == source

    def test_duplicate_definition_reports_diagnostic(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        driver_result = driver.Driver(_PARSER).validate_source(source)
        assert driver_result.result.all_exceptions == []
        all_diagnostics = driver_result.result.all_diagnostics
        assert len(all_diagnostics) == 1
        diagnostic = all_diagnostics[0]
        assert isinstance(diagnostic, diagnostics.DuplicateDefinitionDiagnostic)
        assert diagnostic.definition_type == "position"
        assert diagnostic.path == "/test"
        assert diagnostic.first_definition_line == 1
        assert diagnostic.location.line == 2
        assert diagnostic.location.column == 1


class TestSourceCompilation:
    def test_constructor_entry_point_writes_output(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<output>.\n"
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
            "        create a particle in position<output>.\n"
            "    }\n"
            "}\n"
        )
        driver_result = driver.Driver(_PARSER).compile_source(source, tmp_path)
        assert_no_errors(driver_result.result)
        main_file = tmp_path / "__main__.py"
        assert main_file.exists()
        assert main_file.stat().st_size > 0

    def test_position_entry_point_reports_diagnostic(self, tmp_path: Path):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        driver_result = driver.Driver(_PARSER).compile_source(source, tmp_path)
        assert driver_result.result.all_exceptions == []
        all_diagnostics = driver_result.result.all_diagnostics
        assert len(all_diagnostics) == 1
        diagnostic = all_diagnostics[0]
        assert isinstance(diagnostic, diagnostics.EntryPointNotConstructorDiagnostic)
        assert diagnostic.location.line == 1
        assert diagnostic.location.column == 1

    def test_non_constructor_action_entry_point_reports_diagnostic(
        self, tmp_path: Path
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<trigger>.\n"
            "    it happens when {\n"
            "        the position<trigger> has a particle.\n"
            "    } and it does {\n"
            "        define the position<noop>.\n"
            "        create a particle in position<noop>.\n"
            "    }\n"
            "}\n"
        )
        driver_result = driver.Driver(_PARSER).compile_source(source, tmp_path)
        assert driver_result.result.all_exceptions == []
        all_diagnostics = driver_result.result.all_diagnostics
        assert len(all_diagnostics) == 1
        diagnostic = all_diagnostics[0]
        assert isinstance(diagnostic, diagnostics.EntryPointNotConstructorDiagnostic)
        assert diagnostic.location.line == 1
        assert diagnostic.location.column == 1
