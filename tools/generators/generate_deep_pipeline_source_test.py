# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

import click.testing
import pytest

from define.compiler import driver
from define.compiler.errors import diagnostics
from tools.generators import generate_deep_pipeline_source as gen

if TYPE_CHECKING:
    from pathlib import Path


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
            "create a particle in position<pipeline_0>::action</pipeline_0/process_stage_0>::position<record>::position</temporary_metadata>."
            in source
        )
        assert (
            "move the particle in position<record> to position<next_processing_stage>::action</pipeline_0/process_stage_1>::position<record>."
            in source
        )
        assert (
            "move the particle in position<record> to position<record_processing>::action</pipeline_0/finalize_record>::position<pending_record>."
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
        assert "destroy the particle in position<start>." in source


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        output = tmp_path / "deep_pipeline.dfn"
        written = gen.write_to_path(output, pipelines=2, processing_stages=3)

        assert output.read_text(encoding="utf-8").count("\n") == written


class TestMain:
    def test_writes_source_from_command_line_arguments(self, tmp_path: Path):
        output = tmp_path / "deep_pipeline.dfn"
        result = click.testing.CliRunner().invoke(
            gen.main,
            [
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

        assert result.exit_code == 0
        source = output.read_text(encoding="utf-8")
        assert "action<mv:example.com:profile:/test>" in source
        assert source.count("define the potential action<") == 2 * (3 + 2) + 1

    def test_rejects_invalid_positive_integer(self, tmp_path: Path):
        result = click.testing.CliRunner().invoke(
            gen.main,
            ["--output", str(tmp_path / "source.dfn"), "--pipelines", "0"],
        )

        assert result.exit_code == 2
        assert "0 is not in the range x>=1" in result.output


class TestFullDriver:
    def test_generated_source_passes_full_validation(self):
        source = (
            "\n".join(gen.generate_source_lines(pipelines=1, processing_stages=2))
            + "\n"
        )

        result = driver.Driver().validate_source(source)

        assert result.program_validation.all_exceptions == []
        assert result.program_validation.all_diagnostics == []


class TestValuesAndDestructorReads:
    @pytest.mark.parametrize(
        ("values_per_stage", "destructor_reads"), [(2, False), (0, True), (2, True)]
    )
    def test_generated_source_passes_full_validation(
        self, values_per_stage: int, *, destructor_reads: bool
    ):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    pipelines=2,
                    processing_stages=3,
                    values_per_stage=values_per_stage,
                    destructor_reads=destructor_reads,
                )
            )
            + "\n"
        )

        result = driver.Driver().validate_source(source)

        assert result.program_validation.all_exceptions == []
        assert result.program_validation.all_diagnostics == []

    def test_values_pass_through_every_stage_to_the_final_action(self):
        source = "\n".join(
            gen.generate_source_lines(
                pipelines=2, processing_stages=3, values_per_stage=2
            )
        )

        assert source.count("define the position<value_1> {") == 2 * (3 + 2)
        assert (
            'set the value of position<pipeline_1>::action</pipeline_1/process_stage_0>::position<value_1> from literal<standard:/number>"1".'
            in source
        )
        assert (
            "move the particle in position<value_0> to position<next_processing_stage>::action</pipeline_0/process_stage_2>::position<value_0>."
            in source
        )
        assert (
            "move the particle in position<value_1> to position<record_processing>::action</pipeline_0/finalize_record>::position<value_1>."
            in source
        )
        assert source.count("it also assigns the position</kept_1>.") == 2
        assert (
            source.count("set the value of position</kept_1> from position<value_1>.")
            == 2
        )
        assert "audit" not in source

    def test_destructor_reads_a_value_set_by_the_entry_point(self):
        source = "\n".join(
            gen.generate_source_lines(
                pipelines=2, processing_stages=3, destructor_reads=True
            )
        )

        assert source.count("this particle is being destroyed.") == 1
        assert source.count("it has the action</audit_record>.") == 2 * (3 + 3) + 2
        assert source.count("it has the position</audit_reading>.") == 2
        assert (
            'set the value of position<record_1>::position</audit_reading> from literal<standard:/number>"1".'
            in source
        )
        assert (
            "move the particle in position<record_1> to position<pipeline_1>::action</pipeline_1/process_stage_0>::position<record>."
            in source
        )
        assert source.count("destroy the particle in position<completed_record>.") == 2

    def test_rejects_negative_values_per_stage(self):
        with pytest.raises(ValueError, match="values_per_stage must not be negative"):
            gen.generate_source_lines(values_per_stage=-1)

    def test_cli_writes_values_and_destructor_reads(self, tmp_path: Path):
        output = tmp_path / "deep_pipeline.dfn"
        result = click.testing.CliRunner().invoke(
            gen.main,
            [
                "--output",
                str(output),
                "--pipelines",
                "2",
                "--processing-stages",
                "3",
                "--values-per-stage",
                "2",
                "--destructor-reads",
            ],
        )

        assert result.exit_code == 0
        assert (
            output.read_text(encoding="utf-8")
            == "\n".join(
                gen.generate_source_lines(
                    pipelines=2,
                    processing_stages=3,
                    values_per_stage=2,
                    destructor_reads=True,
                )
            )
            + "\n"
        )


@pytest.mark.parametrize("stages", [1, 4])
def test_violations_have_scalable_propagation_histories(stages: int):
    source = (
        "\n".join(
            gen.generate_source_lines(
                pipelines=2, processing_stages=stages, satisfy_requirements=False
            )
        )
        + "\n"
    )
    result = driver.Driver().validate_source(source)
    assert result.program_validation.all_exceptions == []
    all_diagnostics = result.program_validation.all_diagnostics
    assert len(all_diagnostics) == 2
    for diagnostic in all_diagnostics:
        assert isinstance(
            diagnostic, diagnostics.InferredRequirementViolationDiagnostic
        )
        assert len(diagnostic.propagation_chain) == stages + 3
    assert len(result.error_strings()) == 2


def test_violation_cli(tmp_path: Path):
    output = tmp_path / "violations.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--pipelines",
            "2",
            "--processing-stages",
            "3",
            "--violate-requirements",
        ],
    )
    assert result.exit_code == 0
    assert (
        output.read_text(encoding="utf-8")
        == "\n".join(
            gen.generate_source_lines(
                pipelines=2, processing_stages=3, satisfy_requirements=False
            )
        )
        + "\n"
    )
