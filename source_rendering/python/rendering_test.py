from __future__ import annotations

import textwrap

from source_rendering.python import rendering


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
