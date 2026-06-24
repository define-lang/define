# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, parser
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator
from tools import generate_action_graph_source as gen


def _parse_and_transform(source: str) -> ast.Program:
    par = parser.Parser()
    result = par.parse_and_transform(source, file_path=PurePosixPath("generated.dfn"))
    assert result.exception is None
    assert result.diagnostics == []
    assert result.program is not None
    return result.program


class TestGenerateSourceLines:
    def test_too_few_layers_raises(self):
        with pytest.raises(ValueError, match="layers must be at least"):
            gen.generate_source_lines(layers=1)

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="width must be at least"):
            gen.generate_source_lines(width=0)

    def test_fan_out_larger_than_width_raises(self):
        with pytest.raises(ValueError, match="fan_out must be in"):
            gen.generate_source_lines(width=4, fan_out=5)

    def test_destructor_fraction_out_of_range_raises(self):
        with pytest.raises(ValueError, match="destructor_fraction must be in"):
            gen.generate_source_lines(destructor_fraction=2.0)

    def test_action_count_matches_layers_times_width(self):
        program = _parse_and_transform(
            "\n".join(
                gen.generate_source_lines(
                    layers=3, width=4, fan_out=2, destructor_fraction=0
                )
            )
            + "\n"
        )
        action_count = sum(
            1 for d in program.definitions if isinstance(d, ast.ActionDefinition)
        )
        assert action_count == 3 * 4

    def test_output_exercises_call_graph_syntax(self):
        source = "\n".join(gen.generate_source_lines(layers=3, width=3, fan_out=2))
        assert "define the potential position" in source
        assert "define the potential action" in source
        assert "it may only contain particles where" in source
        assert "this particle is being destroyed" in source
        assert "destroy the particle in position<src>." in source
        assert "create a particle in position<out>::action</layer1_a0>::" in source

    def test_no_destructors_when_fraction_zero(self):
        source = "\n".join(gen.generate_source_lines(destructor_fraction=0))
        assert "this particle is being destroyed" not in source
        assert "marker_destructor" not in source


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        out = tmp_path / "graph.dfn"
        written = gen.write_to_path(out, layers=3, width=3, fan_out=2)
        assert out.read_text(encoding="utf-8").count("\n") == written

    def test_written_file_parses_and_transforms_cleanly(self, tmp_path: Path):
        out = tmp_path / "graph.dfn"
        gen.write_to_path(out, layers=4, width=4, fan_out=2)
        _parse_and_transform(out.read_text(encoding="utf-8"))


class TestFullDriver:
    @pytest.mark.parametrize(
        ("layers", "width", "fan_out", "destructor_fraction"),
        [(3, 3, 2, 0.5), (4, 6, 3, 0.5), (5, 4, 4, 0.0), (3, 5, 5, 1.0)],
    )
    def test_non_filesystem_validation_produces_no_diagnostics(
        self, layers: int, width: int, fan_out: int, destructor_fraction: float
    ):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    layers=layers,
                    width=width,
                    fan_out=fan_out,
                    destructor_fraction=destructor_fraction,
                )
            )
            + "\n"
        )

        pv = program_validator.ProgramStructuralValidator()
        program_result = pv.validate_program_non_filesystem(source)
        reference_graph_validator.ReferenceGraphValidator(
            program_result.reference_graph,
            program_result.definition_results,
        ).validate()

        assert program_result.all_exceptions == []
        assert program_result.all_diagnostics == []
