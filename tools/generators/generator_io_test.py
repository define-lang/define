# pyright: reportUnusedCallResult=false
from pathlib import Path

import pytest

from tools.generators import generator_io


def test_write_lines_replaces_file_and_returns_line_count(tmp_path: Path):
    output = tmp_path / "generated.dfn"
    output.write_text("old content\n", encoding="utf-8")

    written = generator_io.write_lines(output, ["first", "", "third"])

    assert written == 3
    assert output.read_text(encoding="utf-8") == "first\n\nthird\n"


def test_write_lines_preserves_existing_file_when_iteration_fails(tmp_path: Path):
    output = tmp_path / "generated.dfn"
    output.write_text("old content\n", encoding="utf-8")

    def failing_lines():
        yield "first"
        raise ValueError("generation failed")

    with pytest.raises(ValueError, match="generation failed"):
        generator_io.write_lines(output, failing_lines())

    assert output.read_text(encoding="utf-8") == "old content\n"
    assert list(tmp_path.iterdir()) == [output]


def test_write_lines_does_not_create_missing_parent_directories(tmp_path: Path):
    output = tmp_path / "missing" / "generated.dfn"

    with pytest.raises(FileNotFoundError):
        generator_io.write_lines(output, ["source"])

    assert not output.parent.exists()
