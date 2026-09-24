from __future__ import annotations

from define.compiler import ast
from define.compiler.validator.reference_graph import quality_assignment

_LOCATION = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="example.com", location=_LOCATION),
    universe=ast.Universe(name="test", location=_LOCATION),
    location=_LOCATION,
)


def _quality(
    name: str, name_type: ast.NameType = ast.NameType.POSITION
) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=name_type,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=f"/{name}", location=_LOCATION),
            location=_LOCATION,
        ),
        enclosing_fqun=_FQUN,
        location=_LOCATION,
    )


def _build(
    direct: tuple[ast.GlobalTypedNameReference, ...],
    graph: dict[str, tuple[ast.GlobalTypedNameReference, ...]],
) -> quality_assignment.QualityAssignments:
    return quality_assignment.QualityAssignments.expand_implications(
        direct, lambda quality: graph.get(quality.full_typed_name, ())
    )


def test_depth_first_assignment_order():
    first, second, shared, other = map(_quality, ("first", "second", "shared", "other"))
    assignments = _build(
        (first, other),
        {
            first.full_typed_name: (second, other),
            second.full_typed_name: (shared,),
            other.full_typed_name: (shared,),
        },
    )

    assert tuple(assignments) == (shared, second, other, first)


def test_cycles_and_duplicate_reachability_assign_once():
    first, second = map(_quality, ("first", "second"))
    assignments = _build(
        (first, second),
        {
            first.full_typed_name: (second, second),
            second.full_typed_name: (first,),
        },
    )

    assert tuple(assignments) == (second, first)


def test_quality_membership():
    quality = _quality("quality")
    assignments = _build((quality,), {})

    assert assignments.has_quality(quality) is True
    assert assignments.has_quality(_quality("other")) is False
    assert assignments.value_type is None


def test_value_type_with_other_qualities():
    first = _quality("first")
    value = _quality("number", ast.NameType.VALUE)
    last = _quality("last")
    implied = _quality("implied")
    assignments = _build((first, value, last), {last.full_typed_name: (implied,)})

    assert tuple(assignments) == (first, value, implied, last)
    assert assignments.value_type is value
    assert assignments.has_quality(value) is True


def test_shared_empty_collection_is_reused():
    assert _build((), {}) is quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
    assert quality_assignment.EMPTY_QUALITY_ASSIGNMENTS.value_type is None


def test_direct_assignment_value_type():
    position = _quality("position")
    value = _quality("number", ast.NameType.VALUE)
    assignments = quality_assignment.QualityAssignments((position, value))

    assert tuple(assignments) == (position, value)
    assert assignments.value_type is value
    assert assignments.has_quality(position) is True
    assert assignments.has_quality(value) is True


def test_sixty_four_element_chain_is_iterative():
    qualities = tuple(_quality(f"quality_{index}") for index in range(64))
    graph = {
        quality.full_typed_name: (qualities[index + 1],)
        for index, quality in enumerate(qualities[:-1])
    }

    assignments = _build((qualities[0],), graph)

    assert tuple(assignments) == tuple(reversed(qualities))
