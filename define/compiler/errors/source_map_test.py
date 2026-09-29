from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import source_map

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_SOURCE = (
    "define the potential position<my.domain.com:my_lib:/test> {\n"
    "    it may only contain particles where {\n"
    "        it has the position</child>.\n"
    "    }\n"
    "}\n"
)


def _location(
    line: int, column: int, end_column: int, file_path: str | None
) -> ast.SourceLocation:
    return ast.SourceLocation(
        line=line,
        column=column,
        end_line=line,
        end_column=end_column,
        file_path=None if file_path is None else PurePosixPath(file_path),
    )


def _map_for_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> source_map.SourceMap:
    # The compiler reads project files relative to the project root.
    monkeypatch.chdir(tmp_path)
    _ = (tmp_path / "test.dfn").write_text(source, encoding="utf-8")
    return source_map.SourceMap(
        {PurePosixPath("test.dfn"): source_map.source_digest(source.encode())},
        in_memory_source=None,
    )


def test_format_location_underlines_span_with_our_own_indentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    assert sources.format_location(_location(3, 20, 36, "test.dfn")) == (
        'File "test.dfn", line 3, column 20\n'
        "    it has the position</child>.\n"
        "               ^^^^^^^^^^^^^^^^"
    )


def test_format_location_keeps_indentation_when_span_starts_in_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    assert sources.format_location(_location(3, 1, 9, "test.dfn")) == (
        'File "test.dfn", line 3, column 1\n'
        "            it has the position</child>.\n"
        "    ^^^^^^^^"
    )


def test_format_location_underlines_multi_line_span_to_end_of_first_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    location = ast.SourceLocation(
        line=2,
        column=5,
        end_line=4,
        end_column=6,
        file_path=PurePosixPath("test.dfn"),
    )
    assert sources.format_location(location) == (
        'File "test.dfn", line 2, column 5\n'
        "    it may only contain particles where {\n"
        "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
    )


def test_format_location_past_last_line_shows_empty_source_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    assert sources.format_location(_location(9, 1, 2, "test.dfn")) == (
        'File "test.dfn", line 9, column 1\n\n    ^'
    )


def test_format_location_omits_source_line_of_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    _ = (tmp_path / "test.dfn").write_text("# changed\n" + _SOURCE, encoding="utf-8")
    assert sources.format_location(_location(3, 20, 36, "test.dfn")) == (
        'File "test.dfn", line 3, column 20'
    )


def test_format_location_omits_source_line_of_deleted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    (tmp_path / "test.dfn").unlink()
    assert sources.format_location(_location(3, 20, 36, "test.dfn")) == (
        'File "test.dfn", line 3, column 20'
    )


def test_format_location_reads_each_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    first = sources.format_location(_location(3, 20, 36, "test.dfn"))
    (tmp_path / "test.dfn").unlink()
    assert sources.format_location(_location(3, 20, 36, "test.dfn")) == first


def test_format_location_without_file_uses_in_memory_source():
    sources = source_map.SourceMap({}, in_memory_source=_SOURCE)
    assert sources.format_location(_location(2, 5, 40, None)) == (
        "line 2, column 5\n"
        "    it may only contain particles where {\n"
        "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
    )


def test_format_location_without_file_or_in_memory_source_names_location_only():
    sources = source_map.SourceMap({}, in_memory_source=None)
    assert sources.format_location(_location(2, 5, 40, None)) == "line 2, column 5"


def test_format_location_shows_invisible_characters_unescaped():
    sources = source_map.SourceMap({}, in_memory_source="a\u200dbc\n")
    assert sources.format_location(_location(1, 3, 5, None)) == (
        "line 1, column 3\n    a\u200dbc\n      ^^"
    )


def test_format_location_escapes_invisible_characters_and_shifts_underline():
    sources = source_map.SourceMap({}, in_memory_source="a\x01bc\n")
    assert sources.format_location(
        _location(1, 3, 5, None), escape_invisible_characters=True
    ) == ("line 1, column 3\n    a\\x01bc\n         ^^")


def test_format_location_counts_lines_by_newlines_only():
    sources = source_map.SourceMap(
        {}, in_memory_source="first\x0cstill first\nsecond\n"
    )
    assert sources.format_location(_location(2, 1, 7, None)) == (
        "line 2, column 1\n    second\n    ^^^^^^"
    )
