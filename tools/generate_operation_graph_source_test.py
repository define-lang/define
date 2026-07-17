# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, parser
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator
from tools import generate_operation_graph_source as gen


def _parse_and_transform(source: str) -> ast.Program:
    par = parser.Parser()
    result = par.parse_and_transform(source, file_path=PurePosixPath("generated.dfn"))
    assert result.exception is None
    assert result.diagnostics == []
    assert result.program is not None
    return result.program


class TestGenerateSourceLines:
    def test_zero_repetitions_raises(self):
        with pytest.raises(ValueError, match="repetitions must be at least"):
            gen.generate_source_lines(repetitions=0)

    def test_too_short_move_chain_raises(self):
        with pytest.raises(ValueError, match="move_chain_length must be at least"):
            gen.generate_source_lines(move_chain_length=1)

    def test_too_shallow_tree_raises(self):
        with pytest.raises(ValueError, match="tree_depth must be at least"):
            gen.generate_source_lines(tree_depth=1)

    def test_too_few_wide_children_raises(self):
        with pytest.raises(ValueError, match="wide_children must be at least"):
            gen.generate_source_lines(wide_children=1)

    def test_negative_pods_raises(self):
        with pytest.raises(ValueError, match="pods must be at least"):
            gen.generate_source_lines(pods=-1)

    def test_zero_retriggers_raises(self):
        with pytest.raises(ValueError, match="retriggers must be at least"):
            gen.generate_source_lines(retriggers=0)

    def test_output_exercises_operation_graph_syntax(self):
        source = "\n".join(
            gen.generate_source_lines(
                repetitions=2,
                move_chain_length=3,
                tree_depth=2,
                wide_children=3,
                pods=1,
                retriggers=2,
            )
        )
        assert "move the particle in position<rung_0> to position<rung_1>." in source
        assert (
            "move the particle in position<tree_src> to position<tree_dst>." in source
        )
        assert (
            "move the particle in position<side>::position</child_0> to position<side>::position</child_1>."
            in source
        )
        assert "destroy the particle in position<req_1>." in source
        assert (
            "move the particle in position<wpod_0>::action</worker>::position<out> to position<result>."
            in source
        )
        assert (
            "create a particle in position<spod_0>::action</sink>::position<trigger_pos>."
            in source
        )

    def test_no_pod_definitions_when_pods_zero(self):
        source = "\n".join(gen.generate_source_lines(repetitions=1, pods=0))
        assert "worker" not in source
        assert "sink" not in source
        assert "position<result>" not in source


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        out = tmp_path / "opgraph.dfn"
        written = gen.write_to_path(
            out, repetitions=2, move_chain_length=3, tree_depth=2, wide_children=3
        )
        assert out.read_text(encoding="utf-8").count("\n") == written

    def test_written_file_parses_and_transforms_cleanly(self, tmp_path: Path):
        out = tmp_path / "opgraph.dfn"
        gen.write_to_path(
            out, repetitions=2, move_chain_length=3, tree_depth=2, wide_children=3
        )
        _parse_and_transform(out.read_text(encoding="utf-8"))


class TestFullDriver:
    @pytest.mark.parametrize(
        (
            "repetitions",
            "move_chain_length",
            "tree_depth",
            "wide_children",
            "pods",
            "retriggers",
        ),
        [
            (1, 2, 2, 2, 0, 1),
            (2, 4, 3, 4, 2, 2),
            (3, 3, 2, 3, 1, 3),
            (4, 2, 5, 2, 2, 1),
        ],
    )
    def test_non_filesystem_validation_produces_no_diagnostics(
        self,
        repetitions: int,
        move_chain_length: int,
        tree_depth: int,
        wide_children: int,
        pods: int,
        retriggers: int,
    ):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    repetitions=repetitions,
                    move_chain_length=move_chain_length,
                    tree_depth=tree_depth,
                    wide_children=wide_children,
                    pods=pods,
                    retriggers=retriggers,
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
