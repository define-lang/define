# pyright: reportUnusedCallResult=false
from pathlib import Path

import pytest

from define.compiler import driver
from tools.generators import generate_reference_graph_project as gen


class TestGenerateProjectFiles:
    def test_too_few_layers_raises(self):
        with pytest.raises(ValueError, match="layers must be at least"):
            gen.generate_project_files(layers=1)

    def test_fewer_modules_than_layers_raises(self):
        with pytest.raises(ValueError, match="modules must be at least"):
            gen.generate_project_files(modules=4, layers=8)

    def test_zero_fan_out_raises(self):
        with pytest.raises(ValueError, match="fan_out must be at least"):
            gen.generate_project_files(fan_out=0)

    def test_utility_fraction_out_of_range_raises(self):
        with pytest.raises(ValueError, match="utility_fraction must be in"):
            gen.generate_project_files(utility_fraction=1.5)

    def test_writes_one_file_per_module_plus_config_and_entry(self):
        files = gen.generate_project_files(modules=40, layers=4)
        assert len(files) == 42
        assert ".define/project/config.defcl" in files
        assert "test.dfn" in files

    def test_same_seed_generates_identical_files(self):
        first = gen.generate_project_files(modules=40, layers=4, seed=3)
        second = gen.generate_project_files(modules=40, layers=4, seed=3)
        assert first == second

    def test_deepest_layer_definitions_reference_nothing(self):
        files = gen.generate_project_files(modules=40, layers=4)
        assert files["lib/pkg39/m39.dfn"].endswith("m39>.\n")


class TestGeneratedProjectValidates:
    def test_project_validates_without_diagnostics_or_exceptions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        files = gen.generate_project_files(modules=60, layers=5)
        for relative_path, content in files.items():
            file_path = tmp_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = driver.Driver().validate_program(Path("test.dfn")).result

        assert result.all_exceptions == []
        assert result.all_diagnostics == []
