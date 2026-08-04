# pyright: reportUnusedCallResult=false
import sys
from pathlib import Path

import pytest

from define.compiler import driver
from tools.generators import generate_deep_pipeline_source as gen


class TestGenerateSourceLines:
    def test_zero_pipelines_raises(self):
        with pytest.raises(ValueError, match="pipelines must be at least"):
            gen.generate_source_lines(pipelines=0)

    def test_zero_processing_stages_raises(self):
        with pytest.raises(ValueError, match="processing_stages must be at least"):
            gen.generate_source_lines(processing_stages=0)

    def test_output_contains_parent_particle_move_and_child_particle_destroy(self):
        source = "\n".join(gen.generate_source_lines(pipelines=2, processing_stages=3))

        assert source.count("define the potential action<") == 2 * (3 + 2) + 1
        assert (
            "create a particle in position<record_processing>::action</pipeline_0/finalize_record>::position<pending_record>::position</temporary_metadata>."
            in source
        )
        assert (
            "move the particle in position<pending_record> to position<completed_record>."
            in source
        )
        assert (
            "destroy the particle in position<completed_record>::position</temporary_metadata>."
            in source
        )


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        output = tmp_path / "deep_pipeline.dfn"
        written = gen.write_to_path(output, pipelines=2, processing_stages=3)

        assert output.read_text(encoding="utf-8").count("\n") == written


class TestMain:
    def test_writes_source_from_command_line_arguments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        output = tmp_path / "deep_pipeline.dfn"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "generate_deep_pipeline_source",
                "--output",
                str(output),
                "--pipelines",
                "2",
                "--processing-stages",
                "3",
                "--fqun-prefix",
                "mv:example.com:profile",
            ],
        )

        gen.main()

        source = output.read_text(encoding="utf-8")
        assert "action<mv:example.com:profile:/test>" in source
        assert source.count("define the potential action<") == 2 * (3 + 2) + 1


class TestFullCompiler:
    @pytest.mark.parametrize(
        ("pipelines", "processing_stages"),
        [(1, 1), (2, 4), (4, 2)],
    )
    def test_generated_source_compiles_without_diagnostics(
        self, tmp_path: Path, pipelines: int, processing_stages: int
    ):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    pipelines=pipelines,
                    processing_stages=processing_stages,
                )
            )
            + "\n"
        )

        result = driver.Driver().compile_source(source, tmp_path)

        assert result.result.all_exceptions == []
        assert result.result.all_diagnostics == []
