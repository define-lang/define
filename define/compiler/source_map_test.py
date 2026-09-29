from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, source_map

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


def _location(line: int, column: int, file_path: str | None) -> ast.SourceLocation:
    return ast.SourceLocation(
        line=line,
        column=column,
        end_line=line,
        end_column=column + 1,
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


def test_format_location_shows_source_line_and_caret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    assert sources.format_location(_location(3, 20, "test.dfn")) == (
        'File "test.dfn", line 3, column 20\n'
        "        it has the position</child>.\n"
        "                   ^"
    )


def test_format_location_past_last_line_shows_empty_source_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    assert sources.format_location(_location(9, 1, "test.dfn")) == (
        'File "test.dfn", line 9, column 1\n\n^'
    )


def test_format_location_omits_source_line_of_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    _ = (tmp_path / "test.dfn").write_text("# changed\n" + _SOURCE, encoding="utf-8")
    assert sources.format_location(_location(3, 20, "test.dfn")) == (
        'File "test.dfn", line 3, column 20'
    )


def test_format_location_omits_source_line_of_deleted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    (tmp_path / "test.dfn").unlink()
    assert sources.format_location(_location(3, 20, "test.dfn")) == (
        'File "test.dfn", line 3, column 20'
    )


def test_format_location_reads_each_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sources = _map_for_file(tmp_path, monkeypatch, _SOURCE)
    first = sources.format_location(_location(3, 20, "test.dfn"))
    (tmp_path / "test.dfn").unlink()
    assert sources.format_location(_location(3, 20, "test.dfn")) == first


def test_format_location_without_file_uses_in_memory_source():
    sources = source_map.SourceMap({}, in_memory_source=_SOURCE)
    assert sources.format_location(_location(2, 5, None)) == (
        "line 2, column 5\n    it may only contain particles where {\n    ^"
    )


def test_format_location_without_file_or_in_memory_source_names_location_only():
    sources = source_map.SourceMap({}, in_memory_source=None)
    assert sources.format_location(_location(2, 5, None)) == "line 2, column 5"
