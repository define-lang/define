# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import Path, PurePosixPath

import click.testing
import pytest

from define.compiler import ast, driver, parser
from tools.generators import generate_operation_graph_source as gen


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

    @pytest.mark.parametrize("independent_move_branches", [-1, 1])
    def test_invalid_independent_move_branches_raises(
        self, independent_move_branches: int
    ):
        with pytest.raises(
            ValueError, match="independent_move_branches must be zero or at least"
        ):
            gen.generate_source_lines(
                independent_move_branches=independent_move_branches
            )

    def test_too_short_independent_move_chain_raises(self):
        with pytest.raises(
            ValueError, match="independent_move_chain_length must be at least"
        ):
            gen.generate_source_lines(independent_move_chain_length=1)

    def test_output_exercises_operation_graph_syntax(self):
        source = "\n".join(
            gen.generate_source_lines(
                repetitions=2,
                move_chain_length=3,
                tree_depth=2,
                wide_children=3,
                pods=1,
                retriggers=2,
                independent_move_branches=2,
                independent_move_chain_length=3,
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
        assert (
            "move the particle in position<independent_source> to position<independent_stage_0>."
            in source
        )
        assert (
            "move the particle in position<independent_stage_0> to position<independent_workspace>."
            in source
        )
        assert (
            "move the particle in position<independent_workspace> to position<independent_moved_marker>."
            in source
        )
        assert (
            "move the particle in position<independent_workspace>::position</independent_box_1>::position</independent_left> to position<independent_left_holder_1>."
            in source
        )
        assert (
            "destroy the particle in position<independent_workspace>::position</independent_box_1>."
            in source
        )

    def test_no_pod_definitions_when_pods_zero(self):
        source = "\n".join(
            gen.generate_source_lines(
                repetitions=1,
                pods=0,
                independent_move_branches=2,
                independent_move_chain_length=2,
            )
        )
        assert "worker" not in source
        assert "sink" not in source
        assert "position<result>" not in source

    def test_no_independent_move_branches_when_count_zero(self):
        source = "\n".join(
            gen.generate_source_lines(
                repetitions=1,
                pods=0,
                independent_move_branches=0,
                independent_move_chain_length=0,
            )
        )
        assert "independent_" not in source


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        out = tmp_path / "opgraph.dfn"
        written = gen.write_to_path(
            out,
            repetitions=2,
            move_chain_length=3,
            tree_depth=2,
            wide_children=3,
            independent_move_branches=2,
            independent_move_chain_length=2,
        )
        assert out.read_text(encoding="utf-8").count("\n") == written

    def test_written_file_parses_and_transforms_cleanly(self, tmp_path: Path):
        out = tmp_path / "opgraph.dfn"
        gen.write_to_path(
            out,
            repetitions=2,
            move_chain_length=3,
            tree_depth=2,
            wide_children=3,
            independent_move_branches=2,
            independent_move_chain_length=2,
        )
        _parse_and_transform(out.read_text(encoding="utf-8"))


class TestMain:
    def test_writes_source_from_command_line_arguments(self, tmp_path: Path):
        output = tmp_path / "operations.dfn"
        result = click.testing.CliRunner().invoke(
            gen.main,
            [
                "--output",
                str(output),
                "--repetitions",
                "1",
                "--move-chain-length",
                "2",
                "--tree-depth",
                "2",
                "--wide-children",
                "2",
                "--pods",
                "0",
                "--independent-move-branches",
                "2",
                "--independent-move-chain-length",
                "2",
            ],
        )

        assert result.exit_code == 0
        assert output.is_file()


class TestFullDriver:
    def test_generated_source_passes_full_validation(self):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    repetitions=1,
                    move_chain_length=2,
                    tree_depth=2,
                    wide_children=2,
                    pods=1,
                    retriggers=1,
                    independent_move_branches=2,
                    independent_move_chain_length=2,
                )
            )
            + "\n"
        )

        result = driver.Driver().validate_source(source).program_validation

        assert result.all_exceptions == []
        assert result.all_diagnostics == []
