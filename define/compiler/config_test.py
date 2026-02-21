from pathlib import Path, PurePosixPath

import pytest

from defcl.python import exceptions as dcl_exceptions
from define.compiler import config, exceptions


class TestAssertIsProjectRoot:
    def test_raises_when_not_project_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.NotProjectRootError):
            config.assert_is_project_root()

    def test_succeeds_when_config_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text("")
        monkeypatch.chdir(tmp_path)

        config.assert_is_project_root()


class TestProjectConfig:
    def test_valid_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text(
            'project: {\n  universe_name: "test.example.com:my_lib"\n}\n'
        )
        monkeypatch.chdir(tmp_path)

        result = config.project_config()
        assert result.project.universe_name == "test.example.com:my_lib"

    def test_empty_universe_name_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text(
            'project: {\n  universe_name: ""\n}\n'
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.project_config()

    def test_missing_universe_name_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text("project: {}\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.project_config()

    def test_error_message_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text("project: {}\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError) as exc_info:
            _ = config.project_config()

        assert str(exc_info.value) == (
            'File ".define/project/config.defcl"\n'
            "Invalid configuration:\n"
            "  - project.universe_name: value is required"
        )
        assert exc_info.value.config_path == config.CONFIG_PATH
        assert exc_info.value.violation_messages == [
            "project.universe_name: value is required"
        ]


class TestLocalDepsConfig:
    def _write_local_deps(self, tmp_path: Path, content: str) -> None:
        deps_dir = tmp_path / ".define" / "deps"
        deps_dir.mkdir(parents=True, exist_ok=True)
        _ = (deps_dir / "local.defcl").write_text(content)

    def test_valid_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self._write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib"\n'
                "    },\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:core"\n'
                '      path: "vendor/core"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        result = config.local_deps_config()
        assert result == {
            "mv:define-lang.org:lib": PurePosixPath("vendor/lib"),
            "mv:define-lang.org:core": PurePosixPath("vendor/core"),
        }

    def test_missing_file_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)

        result = config.local_deps_config()
        assert result == {}

    def test_empty_deps_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self._write_local_deps(tmp_path, "deps: {}\n")
        monkeypatch.chdir(tmp_path)

        result = config.local_deps_config()
        assert result == {}

    def test_empty_local_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self._write_local_deps(tmp_path, "deps: { local: [] }\n")
        monkeypatch.chdir(tmp_path)

        result = config.local_deps_config()
        assert result == {}

    def test_missing_universe_name_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            'deps: { local: [{ path: "vendor/lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_empty_universe_name_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            'deps: { local: [{ universe_name: "" path: "vendor/lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_missing_path_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self._write_local_deps(
            tmp_path,
            'deps: { local: [{ universe_name: "mv:define-lang.org:lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_absolute_path_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "/absolute/path"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_dotdot_in_path_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "vendor/../lib"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_trailing_slash_in_path_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "vendor/lib/"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError):
            _ = config.local_deps_config()

    def test_duplicate_universe_name_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib"\n'
                "    },\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "other/lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError) as exc_info:
            _ = config.local_deps_config()

        assert exc_info.value.violation_messages == [
            'deps.local: duplicate universe_name "mv:define-lang.org:lib"'
        ]

    def test_error_message_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        self._write_local_deps(
            tmp_path,
            'deps: { local: [{ universe_name: "mv:define-lang.org:lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigValidationError) as exc_info:
            _ = config.local_deps_config()

        assert str(exc_info.value) == (
            'File ".define/deps/local.defcl"\n'
            "Invalid configuration:\n"
            "  - deps.local.path: value is required"
        )
        assert exc_info.value.config_path == config.LOCAL_DEPS_PATH
        assert exc_info.value.violation_messages == [
            "deps.local.path: value is required"
        ]


class TestConfigSyntaxError:
    def test_project_config_syntax_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text(
            "project: { universe_name: 'bad' }\n"
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigSyntaxError) as exc_info:
            _ = config.project_config()

        assert isinstance(exc_info.value.syntax_error, dcl_exceptions.DclSyntaxError)

    def test_local_deps_syntax_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        deps_dir = tmp_path / ".define" / "deps"
        deps_dir.mkdir(parents=True)
        _ = (deps_dir / "local.defcl").write_text(
            "deps: { local: [{ universe_name: 'bad' }] }\n"
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(exceptions.ConfigSyntaxError) as exc_info:
            _ = config.local_deps_config()

        assert isinstance(exc_info.value.syntax_error, dcl_exceptions.DclSyntaxError)
