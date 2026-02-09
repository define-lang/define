# pyright: reportUnusedCallResult=false
"""Tests for the compilation driver."""

from pathlib import Path

import pytest

from define.compiler import diagnostics, driver, parser_exceptions


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
    def test_raises_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        d = driver.Driver()
        with pytest.raises(FileNotFoundError, match="Not a Define project root"):
            d.validate_file(Path("foo.def"))

    def test_error_includes_docs_link(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        d = driver.Driver()
        with pytest.raises(FileNotFoundError, match=r"project-root\.md"):
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
        diags, returned_source = d.validate_file(Path("hello.def"))
        assert diags == []
        assert returned_source == source

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
        diags, _ = d.validate_file(Path("wrong.def"))
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)

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
        diags, _ = d.validate_file(Path("hello.def"))
        assert any(isinstance(d, diagnostics.FqunMismatchDiagnostic) for d in diags)

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
        diags, _ = d.validate_file(Path("sub/dir/leaf.def"))
        assert diags == []
