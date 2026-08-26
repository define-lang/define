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


def _quality(name: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.POSITION,
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


def test_shared_empty_collection_is_reused():
    assert _build((), {}) is quality_assignment.EMPTY_QUALITY_ASSIGNMENTS


def test_sixty_four_element_chain_is_iterative():
    qualities = tuple(_quality(f"quality_{index}") for index in range(64))
    graph = {
        quality.full_typed_name: (qualities[index + 1],)
        for index, quality in enumerate(qualities[:-1])
    }

    assignments = _build((qualities[0],), graph)

    assert tuple(assignments) == tuple(reversed(qualities))
