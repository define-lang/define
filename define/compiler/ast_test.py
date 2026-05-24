# pyright: reportImplicitStringConcatenation=false
"""Tests for AST nodes."""

import sys
from pathlib import PurePosixPath

import pytest

from define.compiler import ast, parser, transformer
from define.compiler.conftest import PositionReferenceFor

_LOC = ast.start_of_file_location()
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
            ast.Multiverse(name=multiverse, location=_LOC)
            if multiverse is not None
            else None
        ),
        authority=(
            ast.Authority(
                name=authority,
                location=_LOC,
            )
            if authority is not None
            else None
        ),
        universe=ast.Universe(name=universe, location=_LOC),
        location=_LOC,
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
        path = ast.GlobalPathName(name="/foo", location=_LOC)
        assert path.relative_path == PurePosixPath("foo")

    def test_relative_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", location=_LOC)
        assert path.relative_path == PurePosixPath("foo/bar/baz")

    def test_file_path_default_root(self):
        path = ast.GlobalPathName(name="/foo", location=_LOC)
        assert path.file_path() == PurePosixPath("foo.dfn")

    def test_file_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", location=_LOC)
        assert path.file_path() == PurePosixPath("foo/bar/baz.dfn")

    def test_file_path_with_root(self):
        path = ast.GlobalPathName(name="/foo", location=_LOC)
        assert path.file_path(PurePosixPath("lib/inner")) == PurePosixPath(
            "lib/inner/foo.dfn"
        )


class TestSourceLocationFromDefinitionName:
    def test_position_spans_keyword_through_close(self):
        name_content = ast.DefinitionGlobalNameContent(
            location=ast.SourceLocation(line=1, column=31, end_line=1, end_column=45),
            fqun=_make_fqun("my_lib", authority="my.domain.com"),
            path=ast.GlobalPathName(location=_LOC, name="/thing"),
        )
        result = ast.SourceLocation.from_definition_name(
            name_content, ast.NameType.POSITION
        )
        assert result == ast.SourceLocation(
            line=1, column=22, end_line=1, end_column=46
        )

    def test_action_spans_keyword_through_close(self):
        name_content = ast.DefinitionGlobalNameContent(
            location=ast.SourceLocation(line=1, column=29, end_line=1, end_column=43),
            fqun=_make_fqun("my_lib", authority="my.domain.com"),
            path=ast.GlobalPathName(location=_LOC, name="/thing"),
        )
        result = ast.SourceLocation.from_definition_name(
            name_content, ast.NameType.ACTION
        )
        assert result == ast.SourceLocation(
            line=1, column=22, end_line=1, end_column=44
        )

    def test_local_position_spans_keyword_through_close(self):
        path = PurePosixPath("foo.dfn")
        name_content = ast.LocalNameContent(
            name="x",
            location=ast.SourceLocation(
                line=2, column=21, end_line=2, end_column=22, file_path=path
            ),
        )
        result = ast.SourceLocation.from_definition_name(
            name_content, ast.NameType.POSITION
        )
        assert result == ast.SourceLocation(
            line=2, column=12, end_line=2, end_column=23, file_path=path
        )


class TestGlobalTypedNameInDefinition:
    def test_full_typed_name(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                location=_LOC,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
        )
        assert typed_name.source_typed_name == "position<my.domain.com:my_lib:/thing>"


class TestGlobalTypedNameReference:
    def test_full_typed_name_with_explicit_fqun(self):
        fqun = _make_fqun("my_lib", authority="my.domain.com")
        reference = ast.GlobalTypedNameReference(
            location=_LOC,
            name_type=ast.NameType.ACTION,
            name_content=ast.ReferenceGlobalNameContent(
                location=_LOC,
                fqun=fqun,
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
            enclosing_fqun=fqun,
        )
        assert reference.full_typed_name == "action<my.domain.com:my_lib:/thing>"

    def test_full_typed_name_with_short_name_uses_enclosing_fqun(self):
        reference = ast.GlobalTypedNameReference(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                location=_LOC,
                fqun=None,
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
            enclosing_fqun=_make_fqun("my_lib", authority="my.domain.com"),
        )
        assert reference.full_typed_name == "position<my.domain.com:my_lib:/thing>"

    def test_full_typed_name_own_fqun_takes_precedence(self):
        reference = ast.GlobalTypedNameReference(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                location=_LOC,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
            enclosing_fqun=_make_fqun("other_lib", authority="other.domain.com"),
        )
        assert reference.full_typed_name == "position<my.domain.com:my_lib:/thing>"


class TestCachedStrings:
    def test_fqun_canonical_is_interned(self):
        fqun = _make_fqun("my_lib", authority="my.domain.com")
        fqun2 = _make_fqun("my_lib", authority="my.domain.com")
        assert fqun.canonical is fqun2.canonical
        assert sys.intern(fqun.canonical) is fqun.canonical

    def test_definition_source_typed_name_returns_same_object(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                location=_LOC,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
        )
        assert typed_name.source_typed_name is typed_name.source_typed_name

    def test_definition_full_typed_name_returns_same_object(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                location=_LOC,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
        )
        assert typed_name.full_typed_name is typed_name.full_typed_name

    def test_definition_source_typed_name_matches_full(self):
        typed_name = ast.GlobalTypedNameInDefinition(
            location=_LOC,
            name_type=ast.NameType.POSITION,
            name_content=ast.DefinitionGlobalNameContent(
                location=_LOC,
                fqun=_make_fqun("my_lib", authority="my.domain.com"),
                path=ast.GlobalPathName(location=_LOC, name="/thing"),
            ),
        )
        assert typed_name.source_typed_name is typed_name.full_typed_name


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


class TestActionIsDestructor:
    def test_destructor_action(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    it happens when {\n"
            "        this dimension point is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.is_destructor is True

    def test_position_presence_action(self):
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
        assert action.is_destructor is False


class TestPositionConstraintTypedNames:
    def test_with_constraints(self):
        position = _parse_position(
            f"define the potential position<{_FQUN}:/a> {{\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</child>.\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        )
        assert [t.full_typed_name for t in position.constraint_typed_names] == [
            f"position<{_FQUN}:/child>",
            f"position<{_FQUN}:/other>",
        ]

    def test_no_constraints(self):
        position = _parse_position(f"define the potential position<{_FQUN}:/a>.\n")
        assert position.constraint_typed_names == []


class TestChainedNameConstruction:
    def test_empty_typed_names_rejected(self):
        with pytest.raises(ValueError, match="at least one typed name"):
            _ = ast.ChainedName(location=_LOC, typed_names=[])


class TestChainedNameCanonical:
    def test_single_element(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>")
        assert pos.canonical_chained_name == "position<local>"

    def test_two_elements(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>")
        assert pos.canonical_chained_name == f"position<local>::position<{_FQUN}:/x>"

    def test_with_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>::position<iface>")
        assert (
            pos.canonical_chained_name
            == f"position<local>::action<{_FQUN}:/act>::position<iface>"
        )


class TestChainedNameCanonicalTuple:
    def test_single_element(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>")
        assert pos.canonical_chained_name_tuple == ("position<local>",)

    def test_three_elements(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>::position<iface>")
        assert pos.canonical_chained_name_tuple == (
            "position<local>",
            f"action<{_FQUN}:/act>",
            "position<iface>",
        )


class TestSourceChainedName:
    def test_single_element(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>")
        assert pos.source_chained_name == "position<local>"

    def test_chained_with_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        assert (
            pos.source_chained_name
            == "position<local>::action</act>::position<iface>::position</child>"
        )


class TestGetLastAction:
    def test_no_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>")
        assert pos.get_last_action() is None

    def test_with_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>::position<iface>")
        result = pos.get_last_action()
        assert result is not None
        assert result.source_typed_name == "action</act>"

    def test_single_element(self, position_reference_for: PositionReferenceFor):
        assert position_reference_for("position<local>").get_last_action() is None

    def test_two_actions(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_last_action()
        assert result is not None
        assert result.source_typed_name == "action</inner>"


class TestGetChainToLastAction:
    def test_no_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>")
        assert pos.get_chain_to_last_action() is None

    def test_with_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>::position<iface>")
        result = pos.get_chain_to_last_action()
        assert result is not None
        assert result.source_chained_name == "position<local>::action</act>"

    def test_two_actions(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_chain_to_last_action()
        assert result is not None
        assert (
            result.source_chained_name
            == "position<local>::action</outer>::position<iface>::action</inner>"
        )


class TestGetLastActionChildren:
    def test_no_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>")
        assert pos.get_last_action_children() is None

    def test_with_action_and_interface(
        self, position_reference_for: PositionReferenceFor
    ):
        pos = position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        result = pos.get_last_action_children()
        assert result is not None
        assert result.source_chained_name == "position<iface>::position</child>"

    def test_action_at_end(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>")
        assert pos.get_last_action_children() is None

    def test_two_actions(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_last_action_children()
        assert result is not None
        assert result.source_chained_name == "position<trigger>"


class TestWalkParentPositions:
    def test_single_element(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>")
        assert list(pos.walk_parent_positions()) == []

    def test_two_positions(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>")
        parents = [p.source_chained_name for p in pos.walk_parent_positions()]
        assert parents == ["position<local>"]

    def test_position_action_position_position(
        self, position_reference_for: PositionReferenceFor
    ):
        pos = position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        parents = [p.source_chained_name for p in pos.walk_parent_positions()]
        assert parents == [
            "position<local>",
            "position<local>::action</act>::position<iface>",
        ]

    def test_three_positions_no_action(
        self, position_reference_for: PositionReferenceFor
    ):
        pos = position_reference_for("position<local>::position</x>::position</y>")
        parents = [p.source_chained_name for p in pos.walk_parent_positions()]
        assert parents == [
            "position<local>",
            "position<local>::position</x>",
        ]


class TestParentPosition:
    def test_single_element(self, position_reference_for: PositionReferenceFor):
        assert position_reference_for("position<local>").parent_position() is None

    def test_two_positions(self, position_reference_for: PositionReferenceFor):
        parent = position_reference_for(
            "position<local>::position</x>"
        ).parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>"

    def test_three_positions(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::position</x>::position</y>")
        parent = pos.parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>::position</x>"

    def test_skips_action(self, position_reference_for: PositionReferenceFor):
        pos = position_reference_for("position<local>::action</act>::position<iface>")
        parent = pos.parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>"

    def test_nearest_parent_includes_action(
        self, position_reference_for: PositionReferenceFor
    ):
        pos = position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        parent = pos.parent_position()
        assert parent is not None
        assert (
            parent.source_chained_name
            == "position<local>::action</act>::position<iface>"
        )

    def test_iterative_walk_leaf_to_root(
        self, position_reference_for: PositionReferenceFor
    ):
        pos = position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        parents: list[str] = []
        current = pos.parent_position()
        while current is not None:
            parents.append(current.source_chained_name)
            current = current.parent_position()
        assert parents == [
            "position<local>::action</act>::position<iface>",
            "position<local>",
        ]


class TestInCaller:
    def test_implied_quality_drops_action_segment(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        caller = position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>"

    def test_implied_quality_chain_drops_action_segment(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>::position</y>")
        caller = position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>::position</y>"

    def test_interface_position_nests_under_action(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position<iface>")
        caller = position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert (
            result.source_chained_name == "position<box>::action</b>::position<iface>"
        )

    def test_implied_action_iface_drops_action_segment(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("action</c>::position<iface>")
        caller = position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert (
            result.source_chained_name == "position<box>::action</c>::position<iface>"
        )

    def test_caller_without_parent_implied_returns_self(
        self, position_reference_for: PositionReferenceFor
    ):
        # When the caller's action chain has no parent position (e.g., an
        # implied action triggered directly), an implied quality lives at
        # the caller's top-level scope, not under any interface position.
        inner = position_reference_for("position</x>")
        caller = position_reference_for("action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position</x>"

    def test_caller_without_parent_interface_concatenates(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position<iface>")
        caller = position_reference_for("action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "action</b>::position<iface>"

    def test_long_caller_chain_implied_drops_trailing_action(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        caller = position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>::position</x>"
        )

    def test_long_caller_chain_interface_concatenates(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position<inner_iface>")
        caller = position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>"
            "::action</bar>::position<inner_iface>"
        )

    def test_two_action_caller_chain_implied_chained_inner(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>::position</y>")
        caller = position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>::position</x>::position</y>"
        )

    def test_two_action_caller_chain_interface_chained_inner(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position<inner_iface>::position</child>")
        caller = position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>"
            "::action</bar>::position<inner_iface>::position</child>"
        )

    def test_position_ending_caller_concatenates_implied(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        caller = position_reference_for("position<box>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>"

    def test_position_ending_caller_concatenates_implied_chain(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>::position</y>")
        caller = position_reference_for("position<box>::position</wrap>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::position</wrap>::position</x>::position</y>"
        )


class TestWithPrefix:
    def test_concatenates_typed_names(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        prefix = position_reference_for("position<box>::action</b>")
        result = inner.with_prefix(prefix)
        assert result.source_chained_name == "position<box>::action</b>::position</x>"

    def test_preserves_position_reference_subclass(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        prefix = position_reference_for("position<box>")
        result = inner.with_prefix(prefix)
        assert isinstance(result, ast.PositionReference)

    def test_preserves_self_location_not_prefix_location(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>")
        prefix = position_reference_for("position<box>")
        result = inner.with_prefix(prefix)
        assert result.location == inner.location
        assert result.location != prefix.location

    def test_multi_element_prefix_and_inner(
        self, position_reference_for: PositionReferenceFor
    ):
        inner = position_reference_for("position</x>::position</y>")
        prefix = position_reference_for("position<box>::position</wrap>")
        result = inner.with_prefix(prefix)
        assert result.source_chained_name == (
            "position<box>::position</wrap>::position</x>::position</y>"
        )
