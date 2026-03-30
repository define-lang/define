# pyright: reportImplicitStringConcatenation=false
"""Tests for AST nodes."""

import sys
from pathlib import PurePosixPath

import pytest

from define.compiler import ast, parser, transformer

_POS = ast.start_of_file_position()
_FQUN = "my.domain.com:my_lib"


def _parse_position(source: str) -> ast.PositionDefinition:
    parse_result = parser.Parser().parse(source)
    assert parse_result.diagnostics == []
    assert parse_result.tree is not None
    program = transformer.DefineTransformer().transform(parse_result.tree)
    definition = program.definitions[0]
    if not isinstance(definition, ast.PositionDefinition):
        raise TypeError(f"Expected PositionDefinition, got {type(definition)}")
    return definition


def _parse_action(source: str) -> ast.ActionDefinition:
    parse_result = parser.Parser().parse(source)
    assert parse_result.diagnostics == []
    assert parse_result.tree is not None
    program = transformer.DefineTransformer().transform(parse_result.tree)
    definition = program.definitions[0]
    if not isinstance(definition, ast.ActionDefinition):
        raise TypeError(f"Expected ActionDefinition, got {type(definition)}")
    return definition


def _make_fqun(
    universe: str,
    authority: str | None = None,
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
                name=authority,
                position=_POS,
            )
            if authority is not None
            else None
        ),
        universe=ast.Universe(name=universe, position=_POS),
        position=_POS,
    )


class TestFqunCanonical:
    def test_universe_only(self):
        assert _make_fqun("standard").canonical == "standard"

    def test_authority_and_universe(self):
        fqun = _make_fqun("my_lib", authority="my.domain.com")
        assert fqun.canonical == "my.domain.com:my_lib"

    def test_multiverse_authority_universe(self):
        fqun = _make_fqun("my_lib", authority="my.domain.com", multiverse="mv")
        assert fqun.canonical == "mv:my.domain.com:my_lib"

    def test_authority_with_path(self):
        fqun = _make_fqun(
            "my_lib",
            authority="my.domain.com/org/team",
        )
        assert fqun.canonical == "my.domain.com/org/team:my_lib"

    def test_authority_with_single_path_segment(self):
        fqun = _make_fqun(
            "my_lib",
            authority="my.domain.com/org",
        )
        assert fqun.canonical == "my.domain.com/org:my_lib"

    def test_multiverse_authority_path_universe(self):
        fqun = _make_fqun(
            "my_lib",
            authority="my.domain.com/org",
            multiverse="mv",
        )
        assert fqun.canonical == "mv:my.domain.com/org:my_lib"


class TestGlobalPathName:
    def test_relative_path_single_segment(self):
        path = ast.GlobalPathName(name="/foo", position=_POS)
        assert path.relative_path == PurePosixPath("foo")

    def test_relative_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", position=_POS)
        assert path.relative_path == PurePosixPath("foo/bar/baz")

    def test_file_path_default_root(self):
        path = ast.GlobalPathName(name="/foo", position=_POS)
        assert path.file_path() == PurePosixPath("foo.def")

    def test_file_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", position=_POS)
        assert path.file_path() == PurePosixPath("foo/bar/baz.def")

    def test_file_path_with_root(self):
        path = ast.GlobalPathName(name="/foo", position=_POS)
        assert path.file_path(PurePosixPath("lib/inner")) == PurePosixPath(
            "lib/inner/foo.def"
        )


class TestGlobalNameContent:
    def test_full_name_with_explicit_fqun(self):
        name = ast.GlobalNameContent(
            position=_POS,
            fqun=_make_fqun("my_lib", authority="my.domain.com"),
            path=ast.GlobalPathName(position=_POS, name="/thing"),
        )
        assert name.full_name() == "my.domain.com:my_lib:/thing"

    def test_full_name_with_in_universe(self):
        name = ast.GlobalNameContent(
            position=_POS,
            fqun=None,
            path=ast.GlobalPathName(position=_POS, name="/thing"),
        )
        assert (
            name.full_name(in_universe=_make_fqun("my_lib", authority="my.domain.com"))
            == "my.domain.com:my_lib:/thing"
        )

    def test_full_name_own_fqun_takes_precedence_over_in_universe(self):
        name = ast.GlobalNameContent(
            position=_POS,
            fqun=_make_fqun("my_lib", authority="my.domain.com"),
            path=ast.GlobalPathName(position=_POS, name="/thing"),
        )
        in_universe = _make_fqun("other_lib", authority="other.domain.com")
        assert name.full_name(in_universe=in_universe) == "my.domain.com:my_lib:/thing"

    def test_full_name_requires_effective_fqun(self):
        name = ast.GlobalNameContent(
            position=_POS,
            fqun=None,
            path=ast.GlobalPathName(position=_POS, name="/thing"),
        )
        with pytest.raises(ValueError, match="requires an effective FQUN"):
            _ = name.full_name()


class TestGlobalTypedNameInDefinition:
    def test_full_typed_name(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        assert typed_name.full_typed_name() == "position<my.domain.com:my_lib:/thing>"


class TestGlobalTypedNameReference:
    def test_full_typed_name_with_explicit_fqun(self):
        reference = ast.GlobalTypedNameReference(
            position=_POS,
            name_type=ast.NameType.ACTION,
            name_content=ast.ReferenceGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        assert reference.full_typed_name() == "action<my.domain.com:my_lib:/thing>"

    def test_full_typed_name_with_short_name_uses_in_universe(self):
        reference = ast.GlobalTypedNameReference(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                position=_POS,
                fqun=None,
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        assert (
            reference.full_typed_name(
                in_universe=_make_fqun("my_lib", authority="my.domain.com")
            )
            == "position<my.domain.com:my_lib:/thing>"
        )

    def test_full_typed_name_own_fqun_takes_precedence(self):
        reference = ast.GlobalTypedNameReference(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        in_universe = _make_fqun("other_lib", authority="other.domain.com")
        assert (
            reference.full_typed_name(in_universe=in_universe)
            == "position<my.domain.com:my_lib:/thing>"
        )


class TestCachedStrings:
    def test_fqun_canonical_is_interned(self):
        fqun = _make_fqun("my_lib", authority="my.domain.com")
        fqun2 = _make_fqun("my_lib", authority="my.domain.com")
        assert fqun.canonical is fqun2.canonical
        assert sys.intern(fqun.canonical) is fqun.canonical

    def test_definition_full_typed_name_returns_same_object(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        assert typed_name.full_typed_name() is typed_name.full_typed_name()

    def test_definition_full_typed_name_ignores_in_universe(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        other = _make_fqun("other_lib", authority="other.domain.com")
        assert (
            typed_name.full_typed_name(in_universe=other)
            is typed_name.full_typed_name()
        )

    def test_definition_source_typed_name_matches_full(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            position=_POS,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                position=_POS,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(position=_POS, name="/thing"),
            ),
        )
        assert typed_name.source_typed_name is typed_name.full_typed_name()


class TestInterfacePositionConstraints:
    def test_with_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</child>.\n"
            "        }\n"
            "    }\n"
            "    define the position<pos_b> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "            it has the position</y>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_position_constraints == {
            "position<pos_a>": frozenset({f"position<{_FQUN}:/child>"}),
            "position<pos_b>": frozenset(
                {
                    f"position<{_FQUN}:/x>",
                    f"position<{_FQUN}:/y>",
                }
            ),
        }

    def test_no_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_position_constraints == {
            "position<pos_a>": frozenset(),
        }

    def test_ignore_later_duplicate_with_different_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</first>.\n"
            "        }\n"
            "    }\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</second>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_position_constraints == {
            "position<pos_a>": frozenset({f"position<{_FQUN}:/first>"}),
        }

    def test_ignore_later_duplicate_that_adds_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a>.\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</second>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_position_constraints == {
            "position<pos_a>": frozenset(),
        }

    def test_no_block(self):
        action = _parse_action(f"define the potential action<{_FQUN}:/act>.\n")
        assert action.interface_position_constraints == {}


class TestPositionConstraintNames:
    def test_with_constraints(self):
        position = _parse_position(
            f"define the potential position<{_FQUN}:/a> {{\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</child>.\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        )
        assert position.constraint_names == frozenset(
            {
                f"position<{_FQUN}:/child>",
                f"position<{_FQUN}:/other>",
            }
        )

    def test_no_constraints(self):
        position = _parse_position(f"define the potential position<{_FQUN}:/a>.\n")
        assert position.constraint_names == frozenset()
