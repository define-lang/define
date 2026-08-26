# pyright: reportUnusedCallResult=false

from __future__ import annotations

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import dead_constraint_tracker

_LOC = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _local_ref(name: str) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.LocalNameContent(name=name, location=_LOC),
        location=_LOC,
    )


def _global_ref(
    path: str, name_type: ast.NameType = ast.NameType.POSITION
) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=name_type,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOC),
            location=_LOC,
        ),
        enclosing_fqun=_FQUN,
        location=_LOC,
    )


def _position_ref(*elements: ast.TypedNameReference) -> ast.PositionReference:
    return ast.PositionReference(typed_names=elements, location=_LOC)


def _action_ref(*elements: ast.TypedNameReference) -> ast.ActionReference:
    return ast.ActionReference(typed_names=elements, location=_LOC)


def _interface_def(
    name: str, constraint_paths: list[str]
) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalNameContent(name=name, location=_LOC),
        location=_LOC,
        constraints=ast.PositionConstraintBlock(
            requirements=tuple(
                ast.PositionRequirementStatement(
                    typed_global_name=_global_ref(path), location=_LOC
                )
                for path in constraint_paths
            ),
            location=_LOC,
        ),
    )


def _definition_name(path: str) -> ast.DefinitionGlobalNameContent:
    return ast.DefinitionGlobalNameContent(
        fqun=_FQUN, path=ast.GlobalPathName(name=path, location=_LOC), location=_LOC
    )


def _position_def(path: str) -> ast.PositionDefinition:
    return ast.PositionDefinition(name=_definition_name(path), location=_LOC)


def _destructor_def(path: str) -> ast.ActionDefinition:
    return ast.ActionDefinition(
        name=_definition_name(path),
        location=_LOC,
        quality_implications=(),
        interface_positions=(),
        trigger_conditions=ast.TriggerConditionsBlock(
            condition=ast.DestructorConditionStatement(location=_LOC),
            location=_LOC,
        ),
        action_statements=ast.ActionStatementsBlock(statements=(), location=_LOC),
    )


def _dead_keys(
    tracker: dead_constraint_tracker.DeadConstraintTracker,
) -> set[tuple[str, str]]:
    candidates = list(tracker.dead_position_constraints())
    candidates.extend(tracker.dead_action_constraints())
    return {candidate.key for candidate in candidates}


def _untriggered_implied_action_names(
    tracker: dead_constraint_tracker.DeadConstraintTracker,
) -> set[str]:
    return {
        implied_action.full_typed_name
        for implied_action in tracker.untriggered_implied_actions()
    }


def test_empty_tracker_has_no_candidates():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    assert not tracker.has_position_constraint_candidates()
    assert not tracker.has_move_candidates()
    assert _dead_keys(tracker) == set()


def test_registered_constraint_is_dead():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    thing = _global_ref("/thing")
    tracker.register_constraint(box, thing)
    assert tracker.has_position_constraint_candidates()
    assert tracker.has_move_candidates()
    assert _dead_keys(tracker) == {("position<box>", thing.full_typed_name)}


def test_register_position_constraints_skips_unresolved_and_destructors():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    position = _interface_def("box", ["/live", "/gone", "/destructo"])
    results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ] = typed_name_dict.TypedNameDict()
    results[_global_ref("/live")] = validation_result.DefinitionValidationResult(
        definition=_position_def("/live")
    )
    results[_global_ref("/destructo")] = validation_result.DefinitionValidationResult(
        definition=_destructor_def("/destructo")
    )
    # "/gone" is intentionally absent: an unresolved constraint.
    tracker.register_position_constraints(position, results)
    assert _dead_keys(tracker) == {
        ("position<box>", _global_ref("/live").full_typed_name)
    }


def test_referenced_child_position_is_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    thing = _global_ref("/thing")
    tracker.register_constraint(box, thing)
    tracker.mark_position_alive(_position_ref(box, thing))
    assert _dead_keys(tracker) == set()


def test_reference_to_action_child_does_not_mark_it_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    coin = _global_ref("/coin", ast.NameType.ACTION)
    tracker.register_constraint(box, coin)
    # Filling an action interface position references it but does not trigger it.
    tracker.mark_position_alive(_position_ref(box, coin, _local_ref("go")))
    assert _dead_keys(tracker) == {("position<box>", coin.full_typed_name)}


def test_triggered_action_is_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    coin = _global_ref("/coin", ast.NameType.ACTION)
    tracker.register_constraint(box, coin)
    tracker.mark_action_alive(_action_ref(box, coin))
    assert _dead_keys(tracker) == set()


def test_reference_to_implied_action_child_does_not_mark_it_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    action = _global_ref("/work", ast.NameType.ACTION)
    tracker.register_implied_action(action)
    tracker.mark_position_alive(_position_ref(action, _local_ref("non_trigger")))
    assert _dead_keys(tracker) == set()
    assert _untriggered_implied_action_names(tracker) == {action.full_typed_name}


def test_triggered_implied_action_is_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    action = _global_ref("/work", ast.NameType.ACTION)
    tracker.register_implied_action(action)
    tracker.mark_action_alive(_action_ref(action))
    assert _untriggered_implied_action_names(tracker) == set()


def test_triggered_action_at_end_of_longer_chain_marks_only_that_action_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    runner = _global_ref("/runner", ast.NameType.ACTION)
    worker = _global_ref("/worker", ast.NameType.ACTION)
    tracker.register_implied_action(runner)
    tracker.register_implied_action(worker)
    tracker.mark_action_alive(_action_ref(runner, _local_ref("iface"), worker))
    assert _untriggered_implied_action_names(tracker) == {runner.full_typed_name}


def test_non_trigger_position_at_end_of_longer_chain_marks_no_action_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    runner = _global_ref("/runner", ast.NameType.ACTION)
    worker = _global_ref("/worker", ast.NameType.ACTION)
    tracker.register_implied_action(runner)
    tracker.register_implied_action(worker)
    tracker.mark_position_alive(
        _position_ref(runner, _local_ref("iface"), worker, _local_ref("non_trigger"))
    )
    assert _untriggered_implied_action_names(tracker) == {
        runner.full_typed_name,
        worker.full_typed_name,
    }


def test_move_required_constraint_is_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    thing = _global_ref("/thing")
    tracker.register_constraint(box, thing)
    tracker.mark_move_required(_position_ref(box), (thing,))
    assert _dead_keys(tracker) == set()


def test_move_required_action_constraint_is_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    action = _global_ref("/work", ast.NameType.ACTION)
    tracker.register_constraint(box, action)
    tracker.mark_move_required(_position_ref(box), (action,))
    assert _dead_keys(tracker) == set()


def test_move_required_action_does_not_mark_an_implication_alive():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    action = _global_ref("/work", ast.NameType.ACTION)
    tracker.register_implied_action(action)
    tracker.mark_move_required(_position_ref(_local_ref("box")), (action,))
    assert _untriggered_implied_action_names(tracker) == {action.full_typed_name}


def test_move_required_marks_only_the_matching_origin():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    thing = _global_ref("/thing")
    tracker.register_constraint(_local_ref("box"), thing)
    tracker.register_constraint(_local_ref("other"), thing)
    tracker.mark_move_required(_position_ref(_local_ref("box")), (thing,))
    assert _dead_keys(tracker) == {("position<other>", thing.full_typed_name)}


def test_move_required_matches_by_name_without_expanding_implications():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    implying = _global_ref("/implying")
    tracker.register_constraint(box, implying)
    # The destination requires the implied quality, not the implying one written
    # on box, so box's constraint stays dead.
    tracker.mark_move_required(_position_ref(box), (_global_ref("/implied"),))
    assert _dead_keys(tracker) == {("position<box>", implying.full_typed_name)}


def test_mark_position_constraints_alive_clears_only_position_candidates():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    iface = _interface_def("iface", ["/a", "/b"])
    for constraint in iface.constraint_typed_names:
        tracker.register_constraint(iface.typed_name, constraint)
    tracker.mark_position_constraints_alive(
        iface.typed_name, iface.constraint_typed_names
    )
    assert _dead_keys(tracker) == set()


def test_mark_position_constraints_alive_does_not_clear_an_action_candidate():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    iface = _interface_def("iface", [])
    action = _global_ref("/work", ast.NameType.ACTION)
    tracker.register_constraint(iface.typed_name, action)
    tracker.mark_position_constraints_alive(iface.typed_name, (action,))
    assert _dead_keys(tracker) == {
        (iface.typed_name.full_typed_name, action.full_typed_name)
    }


def test_one_constraint_alive_while_a_sibling_stays_dead():
    tracker = dead_constraint_tracker.DeadConstraintTracker()
    box = _local_ref("box")
    a = _global_ref("/a")
    b = _global_ref("/b")
    tracker.register_constraint(box, a)
    tracker.register_constraint(box, b)
    tracker.mark_position_alive(_position_ref(box, a))
    assert _dead_keys(tracker) == {("position<box>", b.full_typed_name)}
