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


def test_depth_first_assignment_order_and_paths():
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
    shared_assignment = assignments.preferred_assignment_for(shared)
    assert isinstance(shared_assignment, quality_assignment.ImpliedQualityAssignment)
    second_assignment = shared_assignment.caused_by
    assert second_assignment.quality == second
    assert isinstance(second_assignment, quality_assignment.ImpliedQualityAssignment)
    assert second_assignment.caused_by.quality == first
    assert tuple(
        assignment.quality for assignment in shared_assignment.assignment_path()
    ) == (first, second, shared)


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


def test_later_direct_assignment_is_preferred_without_rewriting_descendant_path():
    first, intermediate, descendant = map(
        _quality, ("first", "intermediate", "descendant")
    )
    assignments = _build(
        (first, intermediate),
        {
            first.full_typed_name: (intermediate,),
            intermediate.full_typed_name: (descendant,),
        },
    )

    preferred = assignments.preferred_assignment_for(intermediate)
    assert type(preferred) is quality_assignment.QualityAssignment
    descendant_assignment = next(
        assignment
        for assignment in assignments.assignments
        if assignment.quality == descendant
    )
    assert isinstance(
        descendant_assignment, quality_assignment.ImpliedQualityAssignment
    )
    assert isinstance(
        descendant_assignment.caused_by,
        quality_assignment.ImpliedQualityAssignment,
    )


def test_preferred_assignment_lookup_and_quality_membership():
    quality = _quality("quality")
    assignments = _build((quality,), {})

    assert assignments.preferred_assignment_for(quality) is assignments.assignments[0]
    assert assignments.assignments[0].assignment_path() == (assignments.assignments[0],)
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
