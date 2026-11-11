from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from source_rendering.python import rendering

if TYPE_CHECKING:
    from pathlib import Path


def test_render_underlines_the_location_after_the_file_header():
    location = rendering.SourceLocation(
        line=2,
        column=11,
        end_line=2,
        end_column=19,
        file_path="config.defcl",
    )
    assert location.render('    name: "example"') == textwrap.dedent("""\
        File "config.defcl", line 2, column 11
            name: "example"
                  ^^^^^^^^^""")


def test_render_without_a_file_path_has_only_the_line_and_column():
    location = rendering.SourceLocation(line=1, column=8, end_line=1, end_column=9)
    assert location.render("count: {}") == textwrap.dedent("""\
        line 1, column 8
            count: {}
                   ^^""")


def test_render_without_a_source_line_is_only_the_header():
    location = rendering.SourceLocation(line=3, column=5, end_line=3, end_column=9)
    assert location.render(None) == "line 3, column 5"


def test_fields():
    location = rendering.SourceLocation(
        line=1,
        column=2,
        end_line=3,
        end_column=4,
        file_path="a.dfn",
    )
    assert location.line == 1
    assert location.column == 2
    assert location.end_line == 3
    assert location.end_column == 4
    assert location.file_path == "a.dfn"


def test_locations_with_the_same_fields_are_equal_and_hash_the_same():
    location = rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=4, file_path="a.dfn"
    )
    same = rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=4, file_path="a.dfn"
    )
    assert location == same
    assert hash(location) == hash(same)


def test_locations_in_different_files_are_not_equal():
    location = rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=4, file_path="a.dfn"
    )
    assert location != rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=4, file_path="b.dfn"
    )
    assert location != rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=4
    )


def test_locations_with_different_positions_are_not_equal():
    location = rendering.SourceLocation(line=1, column=2, end_line=1, end_column=4)
    assert location != rendering.SourceLocation(
        line=1, column=2, end_line=1, end_column=5
    )


def test_a_location_is_not_equal_to_another_type():
    location = rendering.SourceLocation(line=1, column=2, end_line=1, end_column=4)
    assert location != (1, 2, 1, 4)


def test_repr():
    location = rendering.SourceLocation(
        line=1, column=2, end_line=3, end_column=4, file_path="a.dfn"
    )
    assert repr(location) == (
        "SourceLocation(line=1, column=2, end_line=3, end_column=4,"
        + " file_path='a.dfn')"
    )
    assert repr(
        rendering.SourceLocation(line=1, column=2, end_line=3, end_column=4)
    ) == ("SourceLocation(line=1, column=2, end_line=3, end_column=4, file_path=None)")


def test_at_is_another_position_in_the_same_file():
    location = rendering.SourceLocation(
        line=1, column=2, end_line=3, end_column=4, file_path="a.dfn"
    )
    assert location.at(line=5, column=6, end_line=7, end_column=8) == (
        rendering.SourceLocation(
            line=5, column=6, end_line=7, end_column=8, file_path="a.dfn"
        )
    )


def test_at_without_a_file_is_in_no_file():
    location = rendering.SourceLocation(line=1, column=2, end_line=3, end_column=4)
    assert location.at(line=5, column=6, end_line=7, end_column=8).file_path is None


def test_source_map_shows_a_registered_file_s_source_line(tmp_path: Path):
    path = tmp_path / "test.dfn"
    _ = path.write_bytes(b"first\n  second\n")
    sources = rendering.SourceMap()
    sources.register_file(str(path), b"first\n  second\n")
    location = rendering.SourceLocation(
        line=2, column=3, end_line=2, end_column=8, file_path=str(path)
    )
    assert sources.render_location(location) == textwrap.dedent(f"""\
        File "{path}", line 2, column 3
            second
            ^^^^^^""")


def test_source_map_shows_the_in_memory_source_for_a_location_without_a_file():
    sources = rendering.SourceMap(in_memory_source="a b\n")
    location = rendering.SourceLocation(line=1, column=3, end_line=1, end_column=3)
    assert sources.render_location(location) == textwrap.dedent("""\
        line 1, column 3
            a b
              ^""")
