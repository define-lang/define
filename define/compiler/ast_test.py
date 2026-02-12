"""Tests for AST nodes."""

from pathlib import Path

from define.compiler import ast

_POS = ast.SourcePosition(line=1, column=1, end_line=1, end_column=1)


def _make_fqun(
    universe: str,
    authority_domain: str | None = None,
    authority_path: list[str] | None = None,
    multiverse: str | None = None,
) -> ast.Fqun:
    return ast.Fqun(
        multiverse=(
            ast.Multiverse(name=multiverse, position=_POS)
            if multiverse is not None
            else None
        ),
        authority=(
            ast.Authority(
                domain=authority_domain,
                path=authority_path or [],
                position=_POS,
            )
            if authority_domain is not None
            else None
        ),
        universe=ast.Universe(name=universe, position=_POS),
        position=_POS,
    )


class TestFqunCanonical:
    def test_universe_only(self):
        assert _make_fqun("standard").canonical == "standard"

    def test_authority_and_universe(self):
        fqun = _make_fqun("my_lib", authority_domain="my.domain.com")
        assert fqun.canonical == "my.domain.com:my_lib"

    def test_multiverse_authority_universe(self):
        fqun = _make_fqun("my_lib", authority_domain="my.domain.com", multiverse="mv")
        assert fqun.canonical == "mv:my.domain.com:my_lib"

    def test_authority_with_path(self):
        fqun = _make_fqun(
            "my_lib",
            authority_domain="my.domain.com",
            authority_path=["org", "team"],
        )
        assert fqun.canonical == "my.domain.com/org/team:my_lib"

    def test_authority_with_single_path_segment(self):
        fqun = _make_fqun(
            "my_lib",
            authority_domain="my.domain.com",
            authority_path=["org"],
        )
        assert fqun.canonical == "my.domain.com/org:my_lib"

    def test_multiverse_authority_path_universe(self):
        fqun = _make_fqun(
            "my_lib",
            authority_domain="my.domain.com",
            authority_path=["org"],
            multiverse="mv",
        )
        assert fqun.canonical == "mv:my.domain.com/org:my_lib"


def _make_global_path_name(segments: list[str]) -> ast.GlobalPathName:
    return ast.GlobalPathName(
        segments=[ast.GlobalPathNameSegment(name=s, position=_POS) for s in segments],
        position=_POS,
    )


class TestGlobalPathName:
    def test_relative_path_single_segment(self):
        path = _make_global_path_name(["foo"])
        assert path.relative_path == Path("foo")

    def test_relative_path_multiple_segments(self):
        path = _make_global_path_name(["foo", "bar", "baz"])
        assert path.relative_path == Path("foo/bar/baz")

    def test_path_string_single_segment(self):
        path = _make_global_path_name(["foo"])
        assert path.path_string == "/foo"

    def test_path_string_multiple_segments(self):
        path = _make_global_path_name(["foo", "bar"])
        assert path.path_string == "/foo/bar"
