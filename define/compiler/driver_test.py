# pyright: reportUnusedCallResult=false
"""Tests for the compilation driver."""

from pathlib import Path

import pytest

from define.compiler import diagnostics, driver, exceptions, parser_exceptions


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


class TestValidateFileNoProjectRoot:
    def test_raises_project_root_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        d = driver.Driver()
        with pytest.raises(exceptions.NotProjectRootError):
            d.validate_file(Path("foo.def"))

    def test_error_includes_docs_link(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        d = driver.Driver()
        with pytest.raises(exceptions.NotProjectRootError, match=r"project-root\.md"):
            d.validate_file(Path("foo.def"))


class TestValidateFile:
    def test_valid_file_no_diagnostics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        source = "define the potential position<test.example.com:my_lib:/hello>.\n"
        _write_source(tmp_path, "hello.def", source)
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        result = d.validate_file(Path("hello.def"))
        assert result.diagnostics == []
        assert result.source == source
        assert result.file_path == Path("hello.def")

    def test_returns_diagnostics_for_path_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        _write_source(
            tmp_path,
            "wrong.def",
            "define the potential position<test.example.com:my_lib:/other>.\n",
        )
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        result = d.validate_file(Path("wrong.def"))
        assert len(result.diagnostics) == 1
        assert isinstance(result.diagnostics[0], diagnostics.PathMismatchDiagnostic)

    def test_returns_diagnostics_for_fqun_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        _write_source(
            tmp_path,
            "hello.def",
            "define the potential position<other.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        result = d.validate_file(Path("hello.def"))
        assert any(
            isinstance(d, diagnostics.FqunMismatchDiagnostic)
            for d in result.diagnostics
        )

    def test_syntax_error_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _setup_project(tmp_path, "test.example.com:my_lib")
        _write_source(tmp_path, "bad.def", "this is not valid define\n")
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        with pytest.raises(parser_exceptions.DefineSyntaxError):
            d.validate_file(Path("bad.def"))

    def test_nested_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _setup_project(tmp_path, "test.example.com:my_lib")
        _write_source(
            tmp_path,
            "sub/dir/leaf.def",
            "define the potential position<test.example.com:my_lib:/sub/dir/leaf>.\n",
        )
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        result = d.validate_file(Path("sub/dir/leaf.def"))
        assert result.diagnostics == []


class TestPathResolution:
    def test_absolute_path_is_relativized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        _write_source(
            tmp_path,
            "hello.def",
            "define the potential position<test.example.com:my_lib:/hello>.\n",
        )
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        result = d.validate_file(tmp_path / "hello.def")
        assert result.diagnostics == []

    def test_absolute_path_outside_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        _setup_project(project, "test.example.com:my_lib")
        outside = tmp_path / "outside"
        outside.mkdir()
        source_file = outside / "hello.def"
        source_file.write_text(
            "define the potential position<test.example.com:my_lib:/hello>.\n"
        )
        monkeypatch.chdir(project)

        d = driver.Driver()
        with pytest.raises(exceptions.AbsolutePathError) as exc_info:
            d.validate_file(source_file)
        assert exc_info.value.input_path == source_file
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

        d = driver.Driver()
        result = d.validate_file(Path("sub/../hello.def"))
        assert result.diagnostics == []

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

        d = driver.Driver()
        result = d.validate_file(Path("link/hello.def"))
        assert result.diagnostics == []

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
            d.validate_file(Path("link/../hello.def"))
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

        d = driver.Driver()
        result = d.validate_file(Path("link/../hello.def"))
        assert result.diagnostics == []

    def test_path_escaping_project_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_project(tmp_path, "test.example.com:my_lib")
        monkeypatch.chdir(tmp_path)

        d = driver.Driver()
        with pytest.raises(exceptions.RelativePathError) as exc_info:
            d.validate_file(Path("../hello.def"))
        assert exc_info.value.input_path == Path("../hello.def")
        assert exc_info.value.project_root == tmp_path.resolve()
