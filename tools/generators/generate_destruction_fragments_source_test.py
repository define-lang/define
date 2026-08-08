# pyright: reportUnusedCallResult=false
from pathlib import Path

import click.testing
import pytest

from define.compiler import driver
from tools.generators import generate_destruction_fragments_source as gen


class TestGenerateSourceLines:
    def test_zero_callers_raises(self):
        with pytest.raises(ValueError, match="callers must be at least 1"):
            gen.generate_source_lines(callers=0)

    def test_zero_call_depth_raises(self):
        with pytest.raises(ValueError, match="call_depth must be at least 1"):
            gen.generate_source_lines(call_depth=0)

    def test_zero_local_children_raises(self):
        with pytest.raises(ValueError, match="local_children must be at least 1"):
            gen.generate_source_lines(local_children=0)

    def test_zero_repetitions_raises(self):
        with pytest.raises(ValueError, match="repetitions must be at least 1"):
            gen.generate_source_lines(repetitions=0)

    def test_negative_pass_through_actions_raises(self):
        with pytest.raises(ValueError, match="pass_through_actions must be at least 0"):
            gen.generate_source_lines(pass_through_actions=-1)

    def test_emits_local_contributors_pass_throughs_and_repeated_callers(self):
        source = "\n".join(
            gen.generate_source_lines(
                callers=2,
                call_depth=2,
                pass_through_actions=2,
                local_children=1,
                repetitions=2,
            )
        )

        assert "action<mv:define-lang.org:destruction_fragments:/destroyer>" in source
        assert "action</caller_1/pass_1_0>" in source
        assert "action</caller_1/pass_1_1>" in source
        assert "position</fragment_child_caller_0_0_0>" in source
        assert source.count("move the particle in position<source_0_") == 2

    def test_shared_paths_are_defined_once(self):
        source = "\n".join(
            gen.generate_source_lines(
                callers=3,
                call_depth=1,
                pass_through_actions=0,
                local_children=1,
                repetitions=1,
                shared_child_paths=True,
            )
        )

        assert source.count("define the potential position<") == 1
        assert "fragment_child_caller_" not in source


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        output = tmp_path / "destruction_fragments.dfn"
        written = gen.write_to_path(
            output,
            callers=1,
            call_depth=2,
            pass_through_actions=0,
            local_children=1,
            repetitions=1,
        )

        assert output.read_text(encoding="utf-8").count("\n") == written


class TestMain:
    def test_writes_source_from_command_line_arguments(self, tmp_path: Path):
        output = tmp_path / "destruction_fragments.dfn"
        result = click.testing.CliRunner().invoke(
            gen.main,
            [
                "--output",
                str(output),
                "--callers",
                "2",
                "--call-depth",
                "2",
                "--pass-through-actions",
                "0",
                "--local-children",
                "1",
                "--repetitions",
                "1",
                "--shared-child-paths",
                "--fqun-prefix",
                "mv:example.com:profile",
            ],
        )

        assert result.exit_code == 0
        source = output.read_text(encoding="utf-8")
        assert "action<mv:example.com:profile:/test>" in source
        assert "fragment_child_caller_" not in source


class TestFullDriver:
    @pytest.mark.parametrize("path_shape", ["disjoint", "shared"])
    def test_generated_source_passes_full_validation(self, path_shape: str):
        source = (
            "\n".join(
                gen.generate_source_lines(
                    callers=2,
                    call_depth=2,
                    pass_through_actions=1,
                    local_children=2,
                    repetitions=2,
                    shared_child_paths=path_shape == "shared",
                )
            )
            + "\n"
        )

        result = driver.Driver().validate_source(source)

        assert result.result.all_exceptions == []
        assert result.result.all_diagnostics == []
