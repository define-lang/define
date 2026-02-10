from pathlib import Path

import pytest

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
