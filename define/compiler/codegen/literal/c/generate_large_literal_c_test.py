# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.codegen.literal.c import generate_large_literal_c as gen

if TYPE_CHECKING:
    from pathlib import Path


class TestGenerateSourceLines:
    @pytest.mark.parametrize(
        ("shape", "expected"),
        [
            ("compact", "constants[operation]"),
            ("direct", "execution->particles[3]"),
            ("functions", "operation_3"),
            ("regions", "run_region_1"),
            ("switch", "case 3:"),
        ],
    )
    def test_emits_requested_shape(self, shape: gen.CodeShape, expected: str):
        source = "\n".join(
            gen.generate_source_lines(operations=4, shape=shape, region_size=2)
        )

        assert expected in source
        assert "operation_count = 4" in source

    def test_nonpositive_operation_count_raises(self):
        with pytest.raises(ValueError, match="operations must be positive"):
            gen.generate_source_lines(operations=0)

    def test_nonpositive_region_size_raises(self):
        with pytest.raises(ValueError, match="region_size must be positive"):
            gen.generate_source_lines(region_size=0)


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        output = tmp_path / "large.c"
        written = gen.write_to_path(
            output, operations=4, shape="regions", region_size=2
        )

        assert output.read_text(encoding="utf-8").count("\n") == written


class TestMain:
    def test_writes_source_from_command_line_arguments(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        output = tmp_path / "large.c"
        exit_code = gen.main(
            [
                "--output",
                str(output),
                "--operations",
                "8",
                "--shape",
                "switch",
                "--region-size",
                "4",
            ],
        )

        assert exit_code == 0
        source = output.read_text(encoding="utf-8")
        assert capsys.readouterr().out == (
            f"Wrote {source.count(chr(10))} lines to {output}\n"
        )
        assert "operation_count = 8" in source
        assert "case 7:" in source
