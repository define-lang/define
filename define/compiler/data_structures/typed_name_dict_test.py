# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict

_LOC = ast.start_of_file_location()


def _at(line: int) -> ast.SourceLocation:
    return ast.SourceLocation(line=line, column=1, end_line=line, end_column=1)


def _base(name: str, name_type: ast.NameType = ast.NameType.POSITION) -> ast.TypedName:
    return ast.TypedName(
        location=_LOC,
        name_type=name_type,
        name_content=ast.LocalNameContent(location=_LOC, name=name),
    )


def _local(
    name: str,
    name_type: ast.NameType = ast.NameType.POSITION,
    location: ast.SourceLocation = _LOC,
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        location=location,
        name_type=name_type,
        name_content=ast.LocalNameContent(location=location, name=name),
    )


def _fqun(
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
            ast.Authority(name=authority, location=_LOC)
            if authority is not None
            else None
        ),
        universe=ast.Universe(name=universe, location=_LOC),
        location=_LOC,
    )


def _global(
    path: str,
    enclosing_fqun: ast.Fqun,
    fqun: ast.Fqun | None = None,
    name_type: ast.NameType = ast.NameType.POSITION,
) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        location=_LOC,
        name_type=name_type,
        name_content=ast.ReferenceGlobalNameContent(
            location=_LOC,
            fqun=fqun,
            path=ast.GlobalPathName(location=_LOC, name=path),
        ),
        enclosing_fqun=enclosing_fqun,
    )


def _chain(
    *typed_names: ast.TypedNameReference,
    location: ast.SourceLocation = _LOC,
) -> ast.ChainedName:
    return ast.ChainedName(location=location, typed_names=typed_names)


class TestBasicOps:
    def test_setitem_and_getitem(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        assert d[_local("a")] == 1

    def test_contains(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        assert _local("a") in d

    def test_not_contains_initially(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert _local("a") not in d

    def test_contains_non_typed_name_raises(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        with pytest.raises(TypeError):
            _ = "position<a>" in d

    def test_getitem_missing_raises(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        with pytest.raises(KeyError):
            _ = d[_local("a")]

    def test_get_with_default(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert d.get(_local("a"), 99) == 99

    def test_get_existing(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        assert d.get(_local("a"), 99) == 1

    def test_len(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert len(d) == 0
        d[_local("a")] = 1
        d[_local("b")] = 2
        assert len(d) == 2
        del d[_local("a")]
        assert len(d) == 1

    def test_delitem(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        del d[_local("a")]
        assert _local("a") not in d

    def test_delitem_missing_raises(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        with pytest.raises(KeyError):
            del d[_local("a")]

    def test_base_typed_name_key(self):
        d: typed_name_dict.TypedNameDict[ast.TypedName, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_base("a")] = 1
        assert d[_base("a")] == 1

    def test_repr(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        key = _local("a")
        d[key] = 1
        assert repr(d) == f"TypedNameDict({{{key!r}: 1}})"


class TestCanonicalIdentity:
    def test_distinct_instances_same_canonical_collide(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a", location=_at(1))] = 1
        d[_local("a", location=_at(9))] = 2
        assert len(d) == 1
        assert d[_local("a", location=_at(42))] == 2

    def test_global_short_and_full_form_collide(self):
        fqun = _fqun("my_lib", authority="my.domain.com")
        full_form = _global("/thing", enclosing_fqun=fqun, fqun=fqun)
        short_form = _global("/thing", enclosing_fqun=fqun, fqun=None)
        d: typed_name_dict.TypedNameDict[ast.GlobalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[full_form] = 1
        assert d[short_form] == 1
        d[short_form] = 2
        assert len(d) == 1
        assert d[full_form] == 2

    def test_position_and_action_are_distinct(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a", name_type=ast.NameType.POSITION)] = 1
        d[_local("a", name_type=ast.NameType.ACTION)] = 2
        assert len(d) == 2
        assert d[_local("a", name_type=ast.NameType.POSITION)] == 1
        assert d[_local("a", name_type=ast.NameType.ACTION)] == 2

    def test_distinct_names_stay_distinct(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        d[_local("b")] = 2
        assert len(d) == 2

    def test_overwrite_retains_latest_key_instance(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        first = _local("a", location=_at(1))
        second = _local("a", location=_at(9))
        d[first] = 1
        d[second] = 2
        (only_key,) = list(d)
        assert only_key is second


class TestIteration:
    def test_iter_yields_typed_names(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        a = _local("a")
        b = _local("b")
        d[a] = 1
        d[b] = 2
        assert list(d) == [a, b]

    def test_keys(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        a = _local("a")
        b = _local("b")
        d[a] = 1
        d[b] = 2
        assert list(d.keys()) == [a, b]

    def test_items(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        a = _local("a")
        b = _local("b")
        d[a] = 1
        d[b] = 2
        assert list(d.items()) == [(a, 1), (b, 2)]

    def test_values(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        d[_local("b")] = 2
        assert list(d.values()) == [1, 2]

    def test_empty_iteration(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert list(d) == []

    def test_items_view_len_and_contains(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        a = _local("a")
        d[a] = 1
        items = d.items()
        assert len(items) == 1
        assert (a, 1) in items
        assert (a, 2) not in items

    def test_values_view_len_and_contains(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        values = d.values()
        assert len(values) == 1
        assert 1 in values
        assert 2 not in values


class TestInheritedMethods:
    def test_pop(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        assert d.pop(_local("a")) == 1
        assert _local("a") not in d

    def test_setdefault(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert d.setdefault(_local("a"), 7) == 7
        assert d.setdefault(_local("a"), 99) == 7

    def test_clear(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d[_local("a")] = 1
        d.clear()
        assert len(d) == 0

    def test_popitem(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        a = _local("a")
        d[a] = 1
        assert d.popitem() == (a, 1)

    def test_update_from_pairs(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        d.update([(_local("a"), 1), (_local("b"), 2)])
        assert d[_local("a")] == 1
        assert d[_local("b")] == 2

    def test_update_from_mapping(self):
        source: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        source[_local("a")] = 1
        target: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        target.update(source)
        assert target[_local("a")] == 1


class TestEquality:
    def test_equal_across_distinct_key_instances(self):
        left: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        right: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        left[_local("a", location=_at(1))] = 1
        right[_local("a", location=_at(9))] = 1
        assert left == right

    def test_not_equal_different_values(self):
        left: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        right: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        left[_local("a")] = 1
        right[_local("a")] = 2
        assert left != right

    def test_not_equal_different_keys(self):
        left: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        right: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        left[_local("a")] = 1
        right[_local("b")] = 1
        assert left != right

    def test_not_equal_to_non_typed_name_dict(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert d != object()
        assert (d == 5) is False

    def test_unhashable(self):
        d: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        with pytest.raises(TypeError):
            _ = hash(d)


class TestChainedBasicOps:
    def test_setitem_and_getitem(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"), _local("b"))] = 1
        assert d[_chain(_local("a"), _local("b"))] == 1

    def test_contains(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        assert _chain(_local("a")) in d

    def test_not_contains_initially(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert _chain(_local("a")) not in d

    def test_contains_non_chained_name_raises(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        with pytest.raises(TypeError):
            _ = _local("a") in d

    def test_getitem_missing_raises(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        with pytest.raises(KeyError):
            _ = d[_chain(_local("a"))]

    def test_get_with_default(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert d.get(_chain(_local("a")), 99) == 99

    def test_get_existing(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        assert d.get(_chain(_local("a")), 99) == 1

    def test_len(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert len(d) == 0
        d[_chain(_local("a"))] = 1
        d[_chain(_local("b"))] = 2
        assert len(d) == 2
        del d[_chain(_local("a"))]
        assert len(d) == 1

    def test_delitem(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        del d[_chain(_local("a"))]
        assert _chain(_local("a")) not in d

    def test_delitem_missing_raises(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        with pytest.raises(KeyError):
            del d[_chain(_local("a"))]

    def test_repr(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        key = _chain(_local("a"))
        d[key] = 1
        assert repr(d) == f"ChainedNameDict({{{key!r}: 1}})"


class TestChainedCanonicalIdentity:
    def test_distinct_instances_same_canonical_collide(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"), _local("b"), location=_at(1))] = 1
        d[_chain(_local("a"), _local("b"), location=_at(9))] = 2
        assert len(d) == 1
        assert d[_chain(_local("a"), _local("b"), location=_at(42))] == 2

    def test_global_short_and_full_form_collide(self):
        fqun = _fqun("my_lib", authority="my.domain.com")
        full_form = _global("/thing", enclosing_fqun=fqun, fqun=fqun)
        short_form = _global("/thing", enclosing_fqun=fqun, fqun=None)
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(full_form)] = 1
        assert d[_chain(short_form)] == 1
        d[_chain(short_form)] = 2
        assert len(d) == 1
        assert d[_chain(full_form)] == 2

    def test_different_length_chains_are_distinct(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        d[_chain(_local("a"), _local("b"))] = 2
        assert len(d) == 2
        assert d[_chain(_local("a"))] == 1
        assert d[_chain(_local("a"), _local("b"))] == 2

    def test_position_and_action_element_are_distinct(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a", name_type=ast.NameType.POSITION))] = 1
        d[_chain(_local("a", name_type=ast.NameType.ACTION))] = 2
        assert len(d) == 2
        assert d[_chain(_local("a", name_type=ast.NameType.POSITION))] == 1
        assert d[_chain(_local("a", name_type=ast.NameType.ACTION))] == 2

    def test_overwrite_retains_latest_key_instance(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        first = _chain(_local("a"), location=_at(1))
        second = _chain(_local("a"), location=_at(9))
        d[first] = 1
        d[second] = 2
        (only_key,) = list(d)
        assert only_key is second


class TestChainedIteration:
    def test_iter_yields_chained_names(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        a = _chain(_local("a"))
        b = _chain(_local("b"))
        d[a] = 1
        d[b] = 2
        assert list(d) == [a, b]

    def test_keys(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        a = _chain(_local("a"))
        b = _chain(_local("b"))
        d[a] = 1
        d[b] = 2
        assert list(d.keys()) == [a, b]

    def test_items(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        a = _chain(_local("a"))
        b = _chain(_local("b"))
        d[a] = 1
        d[b] = 2
        assert list(d.items()) == [(a, 1), (b, 2)]

    def test_values(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        d[_chain(_local("b"))] = 2
        assert list(d.values()) == [1, 2]

    def test_empty_iteration(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert list(d) == []

    def test_items_view_len_and_contains(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        a = _chain(_local("a"))
        d[a] = 1
        items = d.items()
        assert len(items) == 1
        assert (a, 1) in items
        assert (a, 2) not in items

    def test_values_view_len_and_contains(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        values = d.values()
        assert len(values) == 1
        assert 1 in values
        assert 2 not in values


class TestChainedInheritedMethods:
    def test_pop(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        assert d.pop(_chain(_local("a"))) == 1
        assert _chain(_local("a")) not in d

    def test_setdefault(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert d.setdefault(_chain(_local("a")), 7) == 7
        assert d.setdefault(_chain(_local("a")), 99) == 7

    def test_clear(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d[_chain(_local("a"))] = 1
        d.clear()
        assert len(d) == 0

    def test_popitem(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        a = _chain(_local("a"))
        d[a] = 1
        assert d.popitem() == (a, 1)

    def test_update_from_pairs(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        d.update([(_chain(_local("a")), 1), (_chain(_local("b")), 2)])
        assert d[_chain(_local("a"))] == 1
        assert d[_chain(_local("b"))] == 2

    def test_update_from_mapping(self):
        source: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        source[_chain(_local("a"))] = 1
        target: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        target.update(source)
        assert target[_chain(_local("a"))] == 1


class TestChainedEquality:
    def test_equal_across_distinct_key_instances(self):
        left: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        right: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        left[_chain(_local("a"), location=_at(1))] = 1
        right[_chain(_local("a"), location=_at(9))] = 1
        assert left == right

    def test_not_equal_different_values(self):
        left: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        right: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        left[_chain(_local("a"))] = 1
        right[_chain(_local("a"))] = 2
        assert left != right

    def test_not_equal_different_keys(self):
        left: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        right: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        left[_chain(_local("a"))] = 1
        right[_chain(_local("b"))] = 1
        assert left != right

    def test_not_equal_to_non_chained_name_dict(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        assert d != object()
        assert (d == 5) is False

    def test_not_equal_to_typed_name_dict(self):
        chained: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        typed: typed_name_dict.TypedNameDict[ast.LocalTypedNameReference, int] = (
            typed_name_dict.TypedNameDict()
        )
        assert chained != typed

    def test_unhashable(self):
        d: typed_name_dict.ChainedNameDict[ast.ChainedName, int] = (
            typed_name_dict.ChainedNameDict()
        )
        with pytest.raises(TypeError):
            _ = hash(d)
