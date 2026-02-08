"""Tests for the config loader."""

import pathlib
import tempfile

import pytest

from defcl.python import exceptions
from define.compiler import config_loader


def _write_config(project_root: pathlib.Path, content: str) -> None:
    config_dir = project_root / ".define" / "project"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.defcl"
    config_file.write_text(content)


class TestLoadProjectConfig:
    def test_valid_config(self):
        with tempfile.TemporaryDirectory(prefix="define_test_") as project_root:
            root = pathlib.Path(project_root)
            _write_config(
                root, 'project: {\n  universe_name: "my.domain.com:my_lib"\n}\n'
            )

            result = config_loader.load_project_config(root)
            assert result.project.universe_name == "my.domain.com:my_lib"

    def test_toplevel_scalar_fails(self):
        with tempfile.TemporaryDirectory(prefix="define_test_") as project_root:
            root = pathlib.Path(project_root)
            _write_config(root, 'universe_name: "my.domain.com:my_lib"\n')

            with pytest.raises(exceptions.DclSyntaxError):
                config_loader.load_project_config(root)
