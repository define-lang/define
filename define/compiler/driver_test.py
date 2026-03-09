# pyright: reportUnusedCallResult=false
"""Tests for driver-only behavior."""

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from define.compiler import (
    driver,
    exceptions,
)


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
        _write_source(tmp_path, "sub/test.def", source)
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        driver_result = d.validate_program(Path(PureWindowsPath("sub\\test.def")))
        assert len(driver_result.results) == 1
        result = driver_result.results[0]

        assert result.diagnostics == []
        assert result.exception is None
        assert str(result.file_path) == "sub/test.def"


class TestPathResolution:
    def test_absolute_path_is_relativized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        source_file = _write_source(
            tmp_path,
            "hello.def",
            "define the potential position<test.example.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver().validate_program(source_file)
        assert len(driver_result.results) == 1
        assert driver_result.results[0].exception is None
        assert driver_result.results[0].diagnostics == []
        assert driver_result.results[0].file_path == PurePosixPath("hello.def")

    def test_absolute_path_outside_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        _setup_project(project, "test.example.com:my_lib")
        outside = tmp_path / "outside"
        outside.mkdir()
        source_file = outside / "hello.def"
        monkeypatch.chdir(project)

        d = driver.Driver()
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
            "hello.def",
            "define the potential position<test.example.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver().validate_program(Path("sub/../hello.def"))
        assert len(driver_result.results) == 1
        assert driver_result.results[0].exception is None
        assert driver_result.results[0].diagnostics == []
        assert driver_result.results[0].file_path == PurePosixPath("hello.def")

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
            "hello.def",
            "define the potential position<test.example.com:my_lib:/link/hello>.\n",
        )
        (project / "link").symlink_to(outside)
        monkeypatch.chdir(project)

        driver_result = driver.Driver().validate_program(Path("link/hello.def"))
        assert len(driver_result.results) == 1
        assert driver_result.results[0].exception is None
        assert driver_result.results[0].diagnostics == []
        assert driver_result.results[0].file_path == PurePosixPath("link/hello.def")

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

        d = driver.Driver()
        with pytest.raises(exceptions.RelativePathError) as exc_info:
            d.validate_program(Path("link/../hello.def"))
        assert exc_info.value.input_path == Path("link/../hello.def")
        assert exc_info.value.project_root == project.resolve()

    def test_symlink_with_dotdot_staying_in_root_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        (tmp_path / "real" / "sub").mkdir(parents=True)
        _write_source(
            tmp_path,
            "real/hello.def",
            "define the potential position<test.example.com:my_lib:/real/hello>.\n",
        )
        (tmp_path / "link").symlink_to(tmp_path / "real" / "sub")
        monkeypatch.chdir(tmp_path)

        driver_result = driver.Driver().validate_program(Path("link/../hello.def"))
        assert len(driver_result.results) == 1
        assert driver_result.results[0].exception is None
        assert driver_result.results[0].diagnostics == []
        assert driver_result.results[0].file_path == PurePosixPath("real/hello.def")

    def test_path_escaping_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        with pytest.raises(exceptions.RelativePathError) as exc_info:
            d.validate_program(Path("../hello.def"))
        assert exc_info.value.input_path == Path("../hello.def")
        assert exc_info.value.project_root == tmp_path.resolve()
