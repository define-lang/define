# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, parser
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator
from tools import generate_large_define_source as gen


def _parse_and_transform(source: str) -> ast.Program:
    par = parser.Parser()
    result = par.parse_and_transform(source, file_path=PurePosixPath("generated.dfn"))
    assert result.exception is None
    assert result.diagnostics == []
    assert result.program is not None
    return result.program


class TestGenerateSourceLines:
    def test_minimum_target_raises(self):
        with pytest.raises(ValueError, match="target_lines must be at least"):
            gen.generate_source_lines(50)

    def test_invalid_chain_length_raises(self):
        with pytest.raises(ValueError, match="max_chain_length must be at least 2"):
            gen.generate_source_lines(500, max_chain_length=1)

    def test_invalid_fqun_raises(self):
        with pytest.raises(ValueError, match="fqun must be"):
            gen.generate_source_lines(500, fqun="just_a_path")

    def test_fqun_with_too_few_segments_raises(self):
        with pytest.raises(ValueError, match="fqun prefix must have 2 or 3"):
            gen.generate_source_lines(500, fqun="onlyone:/path")

    def test_fqun_path_must_start_with_slash(self):
        with pytest.raises(ValueError, match="fqun path component must start with"):
            gen.generate_source_lines(500, fqun="authority:universe:notapath")

    def test_small_target_produces_parseable_program(self):
        lines = gen.generate_source_lines(500)
        assert len(lines) >= 500
        program = _parse_and_transform("\n".join(lines) + "\n")
        assert len(program.definitions) >= 3

    def test_output_exercises_diverse_syntax(self):
        source = "\n".join(gen.generate_source_lines(2000)) + "\n"
        assert "define the potential position" in source
        assert "define the potential action" in source
        assert "it may only contain particles where" in source
        assert "it also assigns the" in source
        assert "this particle is created" in source
        assert "this particle is being destroyed" in source
        assert "create a particle in " in source
        assert "move the particle in " in source
        assert "destroy the particle in " in source
        assert "::" in source
        assert "#" in source

    def test_long_chain_present_at_default_max(self):
        lines = gen.generate_source_lines(2000)
        longest_chain_elements = max(line.count("::") + 1 for line in lines)
        assert longest_chain_elements >= gen.DEFAULT_MAX_CHAIN_LENGTH

    def test_custom_max_chain_length_is_honored(self):
        lines = gen.generate_source_lines(2000, max_chain_length=50)
        longest_chain_elements = max(line.count("::") + 1 for line in lines)
        assert longest_chain_elements >= 50
        assert longest_chain_elements <= 50

    def test_multiple_definitions_emitted(self):
        program = _parse_and_transform(
            "\n".join(gen.generate_source_lines(1000)) + "\n"
        )
        assert len(program.definitions) > 5

    def test_custom_fqun_appears_in_main_action(self):
        lines = gen.generate_source_lines(500, fqun="mv:example.com:custom:/entry")
        joined = "\n".join(lines)
        assert "action<mv:example.com:custom:/entry>" in joined


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        out = tmp_path / "big.dfn"
        written = gen.write_to_path(out, 500)
        assert written >= 500
        assert out.read_text(encoding="utf-8").count("\n") == written

    def test_written_file_parses_and_transforms_cleanly(self, tmp_path: Path):
        out = tmp_path / "big.dfn"
        gen.write_to_path(out, 1000, max_chain_length=100)
        _parse_and_transform(out.read_text(encoding="utf-8"))


class TestFullDriver:
    @pytest.mark.parametrize(
        ("target_lines", "max_chain_length"),
        [(500, 10), (1000, 50), (2000, 100)],
    )
    def test_non_filesystem_validation_produces_no_diagnostics(
        self, target_lines: int, max_chain_length: int
    ):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    target_lines, max_chain_length=max_chain_length
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
