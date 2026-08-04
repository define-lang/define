# pyright: reportImplicitStringConcatenation=false
"""Tests for AST nodes."""

import sys
from pathlib import PurePosixPath

import pytest

from define.compiler import ast, test_helpers
from define.compiler.data_structures import define_path

_LOC = ast.start_of_file_location()
_FQUN = "my.domain.com:my_lib"


# These AST tests intentionally construct references from source so their nodes
# follow the same full parser and transformer path as production input.
def _position_reference_for(chained_name: str) -> ast.PositionReference:
    source = (
        f"define the potential action<{_FQUN}:/test> {{\n"
        "    define the position<_trigger>.\n"
        "    it happens when {\n"
        "        the position<_trigger> has a particle.\n"
        "    } and it does {\n"
        f"        create a particle in {chained_name}.\n"
        "    }\n"
        "}\n"
    )
    program = test_helpers.parse_and_transform(source)
    action_definition = program.definitions[0]
    assert isinstance(action_definition, ast.ActionDefinition)
    for statement in action_definition.action_statements.statements:
        if isinstance(statement, ast.CreateParticleStatement):
            return statement.target_position
    raise ValueError(f"No create statement found for: {chained_name}")


def _parse_position(source: str) -> ast.PositionDefinition:
    definition = test_helpers.parse_and_transform(source).definitions[0]
    if not isinstance(definition, ast.PositionDefinition):
        raise TypeError(f"Expected PositionDefinition, got {type(definition)}")
    return definition


def _parse_action(source: str) -> ast.ActionDefinition:
    definition = test_helpers.parse_and_transform(source).definitions[0]
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


class TestSourceFormTypedNameParts:
    def test_local_name(self):
        assert ast.source_form_typed_name_parts("position<item>", _FQUN) == (
            ast.SourceFormTypedNameParts(
                name_type=ast.NameType.POSITION,
                source_name="item",
                is_global=False,
            )
        )

    def test_global_name_in_current_universe_uses_short_source_form(self):
        assert ast.source_form_typed_name_parts(
            "position<my.domain.com:my_lib:/item>",
            _FQUN,
        ) == ast.SourceFormTypedNameParts(
            name_type=ast.NameType.POSITION,
            source_name="/item",
            is_global=True,
        )

    def test_global_name_in_external_multiverse_keeps_full_source_form(self):
        assert ast.source_form_typed_name_parts(
            "action<mv:other.example:other_lib:/run>",
            _FQUN,
        ) == ast.SourceFormTypedNameParts(
            name_type=ast.NameType.ACTION,
            source_name="mv:other.example:other_lib:/run",
            is_global=True,
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
        assert path.relative_path == define_path.DefinePath("foo")

    def test_relative_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", location=_LOC)
        assert path.relative_path == define_path.DefinePath("foo/bar/baz")

    def test_file_path_default_root(self):
        path = ast.GlobalPathName(name="/foo", location=_LOC)
        assert path.file_path() == define_path.DefinePath("foo.dfn")

    def test_file_path_multiple_segments(self):
        path = ast.GlobalPathName(name="/foo/bar/baz", location=_LOC)
        assert path.file_path() == define_path.DefinePath("foo/bar/baz.dfn")

    def test_file_path_with_root(self):
        path = ast.GlobalPathName(name="/foo", location=_LOC)
        assert path.file_path(
            define_path.DefinePath("lib/inner")
        ) == define_path.DefinePath("lib/inner/foo.dfn")


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
            "        it may only contain particles where {\n"
            "            it has the position</child>.\n"
            "        }\n"
            "    }\n"
            "    define the position<pos_b> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "            it has the position</y>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        by_name = action.interface_positions_by_name
        pos_a_constraints = by_name["position<pos_a>"].constraints
        assert pos_a_constraints is not None
        assert pos_a_constraints.as_set == frozenset({f"position<{_FQUN}:/child>"})
        pos_b_constraints = by_name["position<pos_b>"].constraints
        assert pos_b_constraints is not None
        assert pos_b_constraints.as_set == frozenset(
            {
                f"position<{_FQUN}:/x>",
                f"position<{_FQUN}:/y>",
            }
        )

    def test_no_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_positions_by_name["position<pos_a>"].constraints is None

    def test_ignore_later_duplicate_with_different_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</first>.\n"
            "        }\n"
            "    }\n"
            "    define the position<pos_a> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</second>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        constraints = action.interface_positions_by_name["position<pos_a>"].constraints
        assert constraints is not None
        assert constraints.as_set == frozenset({f"position<{_FQUN}:/first>"})

    def test_ignore_later_duplicate_that_adds_constraints(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a>.\n"
            "    define the position<pos_a> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</second>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.interface_positions_by_name["position<pos_a>"].constraints is None


class TestActionIsDestructor:
    def test_destructor_action(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.is_destructor is True

    def test_position_presence_action(self):
        action = _parse_action(
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        assert action.is_destructor is False


class TestPositionConstraintTypedNames:
    def test_with_constraints(self):
        position = _parse_position(
            f"define the potential position<{_FQUN}:/a> {{\n"
            "    it may only contain particles where {\n"
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
        assert position.constraint_typed_names == ()


class TestPositionConstraintBlockAsSet:
    def test_holds_constraint_names(self):
        position = _parse_position(
            f"define the potential position<{_FQUN}:/a> {{\n"
            "    it may only contain particles where {\n"
            "        it has the position</child>.\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        )
        assert position.constraints is not None
        assert position.constraints.as_set == frozenset(
            {f"position<{_FQUN}:/child>", f"position<{_FQUN}:/other>"}
        )


class TestChainedNameConstruction:
    def test_empty_typed_names_rejected(self):
        with pytest.raises(ValueError, match="at least one typed name"):
            _ = ast.ChainedName(location=_LOC, typed_names=())


class TestChainedNameCanonical:
    def test_single_element(self):
        pos = _position_reference_for("position<local>")
        assert pos.canonical_chained_name == "position<local>"

    def test_two_elements(self):
        pos = _position_reference_for("position<local>::position</x>")
        assert pos.canonical_chained_name == f"position<local>::position<{_FQUN}:/x>"

    def test_with_action(self):
        pos = _position_reference_for("position<local>::action</act>::position<iface>")
        assert (
            pos.canonical_chained_name
            == f"position<local>::action<{_FQUN}:/act>::position<iface>"
        )


class TestChainedNameCanonicalTuple:
    def test_single_element(self):
        pos = _position_reference_for("position<local>")
        assert pos.canonical_chained_name_tuple == ("position<local>",)

    def test_three_elements(self):
        pos = _position_reference_for("position<local>::action</act>::position<iface>")
        assert pos.canonical_chained_name_tuple == (
            "position<local>",
            f"action<{_FQUN}:/act>",
            "position<iface>",
        )


class TestSourceChainedName:
    def test_single_element(self):
        pos = _position_reference_for("position<local>")
        assert pos.source_chained_name == "position<local>"

    def test_chained_with_action(self):
        pos = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        assert (
            pos.source_chained_name
            == "position<local>::action</act>::position<iface>::position</child>"
        )


class TestGetLastAction:
    def test_no_action(self):
        pos = _position_reference_for("position<local>::position</x>")
        assert pos.get_last_action() is None

    def test_with_action(self):
        pos = _position_reference_for("position<local>::action</act>::position<iface>")
        result = pos.get_last_action()
        assert result is not None
        assert result.source_typed_name == "action</act>"

    def test_single_element(self):
        assert _position_reference_for("position<local>").get_last_action() is None

    def test_two_actions(self):
        pos = _position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_last_action()
        assert result is not None
        assert result.source_typed_name == "action</inner>"


class TestGetChainToLastAction:
    def test_no_action(self):
        pos = _position_reference_for("position<local>::position</x>")
        assert pos.get_chain_to_last_action() is None

    def test_with_action(self):
        pos = _position_reference_for("position<local>::action</act>::position<iface>")
        result = pos.get_chain_to_last_action()
        assert isinstance(result, ast.ActionReference)
        assert result.source_chained_name == "position<local>::action</act>"

    def test_two_actions(self):
        pos = _position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_chain_to_last_action()
        assert isinstance(result, ast.ActionReference)
        assert (
            result.source_chained_name
            == "position<local>::action</outer>::position<iface>::action</inner>"
        )


class TestGetLastActionChildren:
    def test_no_action(self):
        pos = _position_reference_for("position<local>::position</x>")
        assert pos.get_last_action_children() is None

    def test_with_action_and_interface(self):
        pos = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        result = pos.get_last_action_children()
        assert result is not None
        assert result.source_chained_name == "position<iface>::position</child>"

    def test_action_at_end(self):
        pos = _position_reference_for("position<local>::action</act>")
        assert pos.get_last_action_children() is None

    def test_two_actions(self):
        pos = _position_reference_for(
            "position<local>::action</outer>::position<iface>::action</inner>::position<trigger>"
        )
        result = pos.get_last_action_children()
        assert result is not None
        assert result.source_chained_name == "position<trigger>"


class TestCanonicalPositionPrefixes:
    def test_single_element(self):
        position = _position_reference_for("position<local>")
        assert position.canonical_position_prefixes() == [("position<local>",)]

    def test_two_positions(self):
        position = _position_reference_for("position<local>::position</x>")
        assert position.canonical_position_prefixes() == [
            ("position<local>",),
            ("position<local>", f"position<{_FQUN}:/x>"),
        ]

    def test_position_action_position_position(self):
        position = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        assert position.canonical_position_prefixes() == [
            ("position<local>",),
            ("position<local>", f"action<{_FQUN}:/act>", "position<iface>"),
            (
                "position<local>",
                f"action<{_FQUN}:/act>",
                "position<iface>",
                f"position<{_FQUN}:/child>",
            ),
        ]

    def test_three_positions_no_action(self):
        position = _position_reference_for(
            "position<local>::position</x>::position</y>"
        )
        assert position.canonical_position_prefixes() == [
            ("position<local>",),
            ("position<local>", f"position<{_FQUN}:/x>"),
            ("position<local>", f"position<{_FQUN}:/x>", f"position<{_FQUN}:/y>"),
        ]


class TestPositionPrefix:
    def test_whole_chain_is_self(self):
        position = _position_reference_for("position<local>::position</x>")
        assert position.position_prefix(len(position.typed_names)) is position

    def test_prefix_has_expected_canonical_chained_name(self):
        position = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        canonical_prefix = position.canonical_position_prefixes()[1]
        position_prefix = position.position_prefix(len(canonical_prefix))
        assert position_prefix.canonical_chained_name_tuple == canonical_prefix
        assert (
            position_prefix.source_chained_name
            == "position<local>::action</act>::position<iface>"
        )
        assert position_prefix.location == position.location


class TestParentPosition:
    def test_single_element(self):
        assert _position_reference_for("position<local>").parent_position() is None

    def test_two_positions(self):
        parent = _position_reference_for(
            "position<local>::position</x>"
        ).parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>"

    def test_three_positions(self):
        pos = _position_reference_for("position<local>::position</x>::position</y>")
        parent = pos.parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>::position</x>"

    def test_skips_action(self):
        pos = _position_reference_for("position<local>::action</act>::position<iface>")
        parent = pos.parent_position()
        assert parent is not None
        assert parent.source_chained_name == "position<local>"

    def test_nearest_parent_includes_action(self):
        pos = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        parent = pos.parent_position()
        assert parent is not None
        assert (
            parent.source_chained_name
            == "position<local>::action</act>::position<iface>"
        )

    def test_iterative_walk_leaf_to_root(self):
        pos = _position_reference_for(
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


class TestChainParentPosition:
    def test_single_element(self):
        key = _position_reference_for("position<local>").canonical_chained_name_tuple
        assert ast.chain_parent_position(key) is None

    def test_two_positions(self):
        key = _position_reference_for(
            "position<local>::position</x>"
        ).canonical_chained_name_tuple
        assert ast.chain_parent_position(key) == ("position<local>",)

    def test_skips_action(self):
        key = _position_reference_for(
            "position<local>::action</act>::position<iface>"
        ).canonical_chained_name_tuple
        assert ast.chain_parent_position(key) == ("position<local>",)

    def test_matches_object_form_including_action(self):
        pos = _position_reference_for(
            "position<local>::action</act>::position<iface>::position</child>"
        )
        object_parent = pos.parent_position()
        assert object_parent is not None
        assert (
            ast.chain_parent_position(pos.canonical_chained_name_tuple)
            == object_parent.canonical_chained_name_tuple
        )


class TestIsPrefix:
    def test_equal_chained_name(self):
        chained_name = ("position<parent>", "position<child>")
        assert ast.is_prefix(chained_name, chained_name)

    def test_parent_name(self):
        assert ast.is_prefix(
            ("position<parent>",),
            ("position<parent>", "position<child>"),
        )

    def test_child_name(self):
        assert not ast.is_prefix(
            ("position<parent>", "position<child>"),
            ("position<parent>",),
        )

    def test_different_name(self):
        assert not ast.is_prefix(
            ("position<other>",),
            ("position<parent>", "position<child>"),
        )


class TestChainInCallee:
    def test_interface_position_is_a_child_of_the_action(self):
        caller = _position_reference_for(
            "position<box>::action</b>"
        ).canonical_chained_name_tuple
        absolute = _position_reference_for(
            "position<box>::action</b>::position<iface>"
        ).canonical_chained_name_tuple
        assert ast.chain_in_callee(caller, absolute) == ("position<iface>",)

    def test_implied_position_is_a_child_of_the_actions_parent_position(self):
        caller = _position_reference_for(
            "position<box>::action</b>"
        ).canonical_chained_name_tuple
        absolute = _position_reference_for(
            "position<box>::position</x>"
        ).canonical_chained_name_tuple
        assert ast.chain_in_callee(caller, absolute) == (
            "position<my.domain.com:my_lib:/x>",
        )

    def test_inverts_chain_in_caller(self):
        caller = _position_reference_for(
            "position<box>::action</b>"
        ).canonical_chained_name_tuple
        for source in (
            "position<iface>",
            "position</x>",
            "position</x>::position</y>",
            "action</c>::position<iface>",
        ):
            local = _position_reference_for(source).canonical_chained_name_tuple
            assert (
                ast.chain_in_callee(caller, ast.chain_in_caller(caller, local)) == local
            )


class TestInCaller:
    def test_implied_quality_drops_action_segment(self):
        inner = _position_reference_for("position</x>")
        caller = _position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>"

    def test_implied_quality_chain_drops_action_segment(self):
        inner = _position_reference_for("position</x>::position</y>")
        caller = _position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>::position</y>"

    def test_interface_position_nests_under_action(self):
        inner = _position_reference_for("position<iface>")
        caller = _position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert (
            result.source_chained_name == "position<box>::action</b>::position<iface>"
        )

    def test_implied_action_iface_drops_action_segment(self):
        inner = _position_reference_for("action</c>::position<iface>")
        caller = _position_reference_for("position<box>::action</b>")
        result = inner.in_caller(caller)
        assert (
            result.source_chained_name == "position<box>::action</c>::position<iface>"
        )

    def test_caller_without_parent_implied_returns_self(self):
        # When the caller's action chain has no parent position (e.g., an
        # implied action triggered directly), an implied quality lives at
        # the caller's top-level scope, not under any interface position.
        inner = _position_reference_for("position</x>")
        caller = _position_reference_for("action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position</x>"

    def test_caller_without_parent_interface_concatenates(self):
        inner = _position_reference_for("position<iface>")
        caller = _position_reference_for("action</b>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "action</b>::position<iface>"

    def test_long_caller_chain_implied_drops_trailing_action(self):
        inner = _position_reference_for("position</x>")
        caller = _position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>::position</x>"
        )

    def test_long_caller_chain_interface_concatenates(self):
        inner = _position_reference_for("position<inner_iface>")
        caller = _position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>"
            "::action</bar>::position<inner_iface>"
        )

    def test_two_action_caller_chain_implied_chained_inner(self):
        inner = _position_reference_for("position</x>::position</y>")
        caller = _position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>::position</x>::position</y>"
        )

    def test_two_action_caller_chain_interface_chained_inner(self):
        inner = _position_reference_for("position<inner_iface>::position</child>")
        caller = _position_reference_for(
            "position<box>::action</foo>::position<iface>::action</bar>"
        )
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::action</foo>::position<iface>"
            "::action</bar>::position<inner_iface>::position</child>"
        )

    def test_position_ending_caller_concatenates_implied(self):
        inner = _position_reference_for("position</x>")
        caller = _position_reference_for("position<box>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == "position<box>::position</x>"

    def test_position_ending_caller_concatenates_implied_chain(self):
        inner = _position_reference_for("position</x>::position</y>")
        caller = _position_reference_for("position<box>::position</wrap>")
        result = inner.in_caller(caller)
        assert result.source_chained_name == (
            "position<box>::position</wrap>::position</x>::position</y>"
        )


class TestWithPrefix:
    def test_concatenates_typed_names(self):
        inner = _position_reference_for("position</x>")
        prefix = _position_reference_for("position<box>::action</b>")
        result = inner.with_prefix(prefix)
        assert result.source_chained_name == "position<box>::action</b>::position</x>"

    def test_preserves_position_reference_subclass(self):
        inner = _position_reference_for("position</x>")
        prefix = _position_reference_for("position<box>")
        result = inner.with_prefix(prefix)
        assert isinstance(result, ast.PositionReference)

    def test_preserves_self_location_not_prefix_location(self):
        inner = _position_reference_for("position</x>")
        prefix = _position_reference_for("position<box>")
        result = inner.with_prefix(prefix)
        assert result.location == inner.location
        assert result.location != prefix.location

    def test_multi_element_prefix_and_inner(self):
        inner = _position_reference_for("position</x>::position</y>")
        prefix = _position_reference_for("position<box>::position</wrap>")
        result = inner.with_prefix(prefix)
        assert result.source_chained_name == (
            "position<box>::position</wrap>::position</x>::position</y>"
        )


def _action_typed_name(path: str) -> ast.GlobalTypedNameReference:
    fqun = _make_fqun("my_lib", authority="my.domain.com")
    return ast.GlobalTypedNameReference(
        location=_LOC,
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            location=_LOC,
            fqun=fqun,
            path=ast.GlobalPathName(location=_LOC, name=path),
        ),
        enclosing_fqun=fqun,
    )


class TestActionReference:
    def test_rejects_chain_ending_in_position(self):
        pos = _position_reference_for("position<local>::position</x>")
        with pytest.raises(ValueError, match="must be an action"):
            _ = ast.ActionReference(location=pos.location, typed_names=pos.typed_names)

    def test_accepts_chain_ending_in_action(self):
        action = _action_typed_name("/act")
        result = ast.ActionReference(location=_LOC, typed_names=(action,))
        assert result.source_chained_name == "action<my.domain.com:my_lib:/act>"


class TestWithSuffix:
    def test_with_position_suffix_returns_position_reference(self):
        base = _position_reference_for("position<box>::action</act>::position<iface>")
        suffix = _position_reference_for("position</child>")
        result = base.with_position_suffix(*suffix.typed_names)
        assert isinstance(result, ast.PositionReference)
        assert result.source_chained_name == (
            "position<box>::action</act>::position<iface>::position</child>"
        )

    def test_with_position_suffix_rejects_action_suffix(self):
        base = _position_reference_for("position<box>")
        with pytest.raises(ValueError, match="must be a position"):
            _ = base.with_position_suffix(_action_typed_name("/act"))

    def test_with_action_suffix_returns_action_reference(self):
        base = _position_reference_for("position<box>")
        result = base.with_action_suffix(_action_typed_name("/act"))
        assert isinstance(result, ast.ActionReference)
        assert result.source_chained_name == (
            "position<box>::action<my.domain.com:my_lib:/act>"
        )

    def test_with_action_suffix_rejects_position_suffix(self):
        base = _position_reference_for("position<box>")
        with pytest.raises(ValueError, match="must be an action"):
            _ = base.with_action_suffix(*base.typed_names)
