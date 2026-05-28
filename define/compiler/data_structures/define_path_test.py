# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler.data_structures import define_path


class TestConstruction:
    def test_str_round_trip(self):
        assert str(define_path.DefinePath("foo/bar")) == "foo/bar"

    def test_no_normalization_trailing_slash(self):
        assert str(define_path.DefinePath("foo/")) == "foo/"

    def test_no_normalization_dot_segment(self):
        assert str(define_path.DefinePath("a/./b")) == "a/./b"

    def test_empty_string(self):
        assert str(define_path.DefinePath("")) == ""

    def test_absolute(self):
        assert str(define_path.DefinePath("/foo/bar")) == "/foo/bar"


class TestTrueDiv:
    def test_relative_with_relative(self):
        assert define_path.DefinePath("a") / define_path.DefinePath(
            "b"
        ) == define_path.DefinePath("a/b")

    def test_absolute_self_with_relative(self):
        assert define_path.DefinePath("/a") / define_path.DefinePath(
            "b"
        ) == define_path.DefinePath("/a/b")

    def test_trailing_slash_on_self_stripped(self):
        assert define_path.DefinePath("a/") / define_path.DefinePath(
            "b"
        ) == define_path.DefinePath("a/b")

    def test_leading_slash_on_right_stripped(self):
        assert define_path.DefinePath("a") / define_path.DefinePath(
            "/b"
        ) == define_path.DefinePath("a/b")

    def test_both_absolute_join_concatenates(self):
        assert define_path.DefinePath("/a") / define_path.DefinePath(
            "/b"
        ) == define_path.DefinePath("/a/b")

    def test_root_self_with_relative(self):
        assert define_path.DefinePath("/") / define_path.DefinePath(
            "foo"
        ) == define_path.DefinePath("/foo")

    def test_root_self_with_absolute(self):
        assert define_path.DefinePath("/") / define_path.DefinePath(
            "/foo"
        ) == define_path.DefinePath("/foo")

    def test_root_joined_with_root(self):
        assert define_path.DefinePath("/") / define_path.DefinePath(
            "/"
        ) == define_path.DefinePath("/")


class TestParts:
    def test_absolute_path(self):
        assert define_path.DefinePath("/foo/bar").parts == ["", "foo", "bar"]

    def test_relative_path(self):
        assert define_path.DefinePath("foo/bar").parts == ["foo", "bar"]

    def test_root(self):
        assert define_path.DefinePath("/").parts == ["", ""]

    def test_single_segment(self):
        assert define_path.DefinePath("foo").parts == ["foo"]

    def test_trailing_slash(self):
        assert define_path.DefinePath("a/").parts == ["a", ""]

    def test_empty(self):
        assert define_path.DefinePath("").parts == []


class TestName:
    def test_no_slash(self):
        assert define_path.DefinePath("foo").name == "foo"

    def test_with_slash(self):
        assert define_path.DefinePath("foo/bar").name == "bar"

    def test_trailing_slash(self):
        assert define_path.DefinePath("foo/").name == ""

    def test_root(self):
        assert define_path.DefinePath("/").name == ""

    def test_empty(self):
        assert define_path.DefinePath("").name == ""


class TestWithSuffix:
    def test_appends_to_path_without_suffix(self):
        assert define_path.DefinePath("foo/bar").with_suffix(
            ".dfn"
        ) == define_path.DefinePath("foo/bar.dfn")

    def test_appends_even_when_suffix_exists(self):
        assert define_path.DefinePath("foo/bar.txt").with_suffix(
            ".dfn"
        ) == define_path.DefinePath("foo/bar.txt.dfn")

    def test_empty_suffix_is_no_op(self):
        assert define_path.DefinePath("foo/bar").with_suffix(
            ""
        ) == define_path.DefinePath("foo/bar")

    def test_appends_to_double_dotted(self):
        assert define_path.DefinePath("foo.tar").with_suffix(
            ".gz"
        ) == define_path.DefinePath("foo.tar.gz")

    def test_root_appends_suffix(self):
        assert define_path.DefinePath("/").with_suffix(
            ".dfn"
        ) == define_path.DefinePath("/.dfn")

    def test_root_with_empty_suffix(self):
        assert define_path.DefinePath("/").with_suffix("") == define_path.DefinePath(
            "/"
        )


class TestAsRelativePath:
    def test_strips_leading_slash(self):
        assert (
            define_path.DefinePath("foo/bar")
            == define_path.DefinePath("/foo/bar").as_relative_path()
        )

    def test_relative_returns_self(self):
        path = define_path.DefinePath("foo/bar")
        assert path is path.as_relative_path()

    def test_root_becomes_empty(self):
        assert define_path.DefinePath("/").as_relative_path() == define_path.EMPTY

    def test_empty_returns_self(self):
        assert define_path.EMPTY is define_path.EMPTY.as_relative_path()

    def test_strips_only_one_slash(self):
        assert (
            define_path.DefinePath("/foo")
            == define_path.DefinePath("//foo").as_relative_path()
        )


class TestAsPosixPath:
    def test_returns_pure_posix_path(self):
        assert isinstance(
            define_path.DefinePath("foo/bar").as_posix_path(), PurePosixPath
        )

    def test_relative(self):
        assert (
            PurePosixPath("foo/bar")
            == define_path.DefinePath("foo/bar").as_posix_path()
        )

    def test_absolute(self):
        assert (
            PurePosixPath("/foo/bar")
            == define_path.DefinePath("/foo/bar").as_posix_path()
        )

    def test_root(self):
        assert PurePosixPath("/") == define_path.DefinePath("/").as_posix_path()


class TestDefinePathFromPosix:
    def test_str_matches_source(self):
        assert str(define_path.DefinePathFromPosix(PurePosixPath("/foo/bar"))) == (
            "/foo/bar"
        )

    def test_as_posix_path_returns_original_object(self):
        source = PurePosixPath("/foo/bar")
        assert source is define_path.DefinePathFromPosix(source).as_posix_path()

    def test_inherits_parts(self):
        assert define_path.DefinePathFromPosix(PurePosixPath("/foo/bar")).parts == [
            "",
            "foo",
            "bar",
        ]

    def test_inherits_name(self):
        assert define_path.DefinePathFromPosix(PurePosixPath("/foo/bar")).name == "bar"

    def test_inherits_with_suffix(self):
        assert define_path.DefinePath(
            "/foo/bar.dfn"
        ) == define_path.DefinePathFromPosix(PurePosixPath("/foo/bar")).with_suffix(
            ".dfn"
        )


class TestInvalidDefinePath:
    def test_str(self):
        assert str(define_path.InvalidDefinePath("<string>")) == "<string>"

    def test_name(self):
        assert define_path.InvalidDefinePath("<string>").name == "<string>"

    def test_truediv_raises(self):
        invalid = define_path.InvalidDefinePath("<string>")
        with pytest.raises(define_path.InvalidPathError):
            _ = invalid / define_path.DefinePath("foo")

    def test_parts_raises(self):
        invalid = define_path.InvalidDefinePath("<string>")
        with pytest.raises(define_path.InvalidPathError):
            _ = invalid.parts

    def test_with_suffix_raises(self):
        invalid = define_path.InvalidDefinePath("<string>")
        with pytest.raises(define_path.InvalidPathError):
            _ = invalid.with_suffix(".dfn")

    def test_as_relative_path_raises(self):
        invalid = define_path.InvalidDefinePath("<string>")
        with pytest.raises(define_path.InvalidPathError):
            _ = invalid.as_relative_path()

    def test_as_posix_path_raises(self):
        invalid = define_path.InvalidDefinePath("<string>")
        with pytest.raises(define_path.InvalidPathError):
            _ = invalid.as_posix_path()


class TestEquality:
    def test_equal_paths(self):
        assert define_path.DefinePath("a/b") == define_path.DefinePath("a/b")

    def test_unequal_paths(self):
        assert define_path.DefinePath("a") != define_path.DefinePath("b")

    def test_trailing_slash_makes_distinct(self):
        assert define_path.DefinePath("foo") != define_path.DefinePath("foo/")

    def test_hashable(self):
        assert hash(define_path.DefinePath("a/b")) == hash(
            define_path.DefinePath("a/b")
        )

    def test_usable_as_dict_key(self):
        d: dict[define_path.DefinePath, int] = {define_path.DefinePath("a"): 1}
        assert d[define_path.DefinePath("a")] == 1

    def test_usable_as_set_member(self):
        s = {
            define_path.DefinePath("a"),
            define_path.DefinePath("b"),
            define_path.DefinePath("a"),
        }
        assert s == {define_path.DefinePath("a"), define_path.DefinePath("b")}

    def test_plain_equals_from_posix(self):
        assert define_path.DefinePath("foo/bar") == define_path.DefinePathFromPosix(
            PurePosixPath("foo/bar")
        )

    def test_dict_lookup_across_subclasses(self):
        d: dict[define_path.DefinePath, int] = {
            define_path.DefinePathFromPosix(PurePosixPath("foo")): 1
        }
        assert d[define_path.DefinePath("foo")] == 1


class TestEmpty:
    def test_str(self):
        assert str(define_path.EMPTY) == ""

    def test_equals_empty_string_path(self):
        assert define_path.DefinePath("") == define_path.EMPTY

    def test_parts(self):
        assert define_path.EMPTY.parts == []

    def test_name(self):
        assert define_path.EMPTY.name == ""

    def test_join_with_relative_returns_relative(self):
        assert define_path.DefinePath("foo") == (
            define_path.EMPTY / define_path.DefinePath("foo")
        )

    def test_join_with_absolute_preserves_leading_slash(self):
        assert define_path.DefinePath("/foo") == (
            define_path.EMPTY / define_path.DefinePath("/foo")
        )

    def test_join_with_empty_right_returns_left(self):
        assert define_path.DefinePath("foo/bar/baz") == (
            define_path.DefinePath("foo/bar/baz") / define_path.EMPTY
        )

    def test_empty_join_empty(self):
        assert define_path.EMPTY == define_path.EMPTY / define_path.EMPTY

    def test_with_suffix_appends(self):
        assert define_path.DefinePath(".dfn") == define_path.EMPTY.with_suffix(".dfn")
