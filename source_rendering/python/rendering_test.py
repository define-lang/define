from __future__ import annotations

import textwrap

from source_rendering.python import rendering


def test_render_location_underlines_the_location_after_the_file_header():
    assert rendering.render_location(
        line=2,
        column=11,
        end_line=2,
        end_column=19,
        source_line='    name: "example"',
        file_path="config.defcl",
    ) == textwrap.dedent("""\
        File "config.defcl", line 2, column 11
            name: "example"
                  ^^^^^^^^^""")


def test_render_location_without_a_source_line_is_only_the_header():
    assert (
        rendering.render_location(
            line=3,
            column=5,
            end_line=3,
            end_column=9,
            source_line=None,
            file_path=None,
        )
        == "line 3, column 5"
    )
