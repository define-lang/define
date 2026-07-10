# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors

_MAIN_FQUN_NAME = "my.domain.com:my_lib"
_DEP_FQUN_NAME = "other.com:other_lib"


def _parse_action(
    source: str,
    action_name: str = f"action<{_MAIN_FQUN_NAME}:/test>",
) -> ast.ActionDefinition:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)
    definition = next(
        definition_result.definition
        for definition_result in result.definition_results.values()
        if definition_result.definition.typed_name.full_typed_name == action_name
    )
    assert isinstance(definition, ast.ActionDefinition)
    return definition


def _get_fqun(action: ast.ActionDefinition) -> ast.Fqun:
    return action.typed_name.name_content.fqun


def _get_create_ref(
    action: ast.ActionDefinition, index: int = 0
) -> ast.PositionReference:
    creates = [
        stmt
        for stmt in action.action_statements.statements
        if isinstance(stmt, ast.CreateParticleStatement)
    ]
    return creates[index].target_position


def _resolved(req: action_contract.PositionRequirement, fqun: ast.Fqun) -> str:
    return req.position.source_form_in_universe(fqun)


_EMPTY = action_contract.PositionOccupancyState.EMPTY

_OUTER = _parse_action(
    (
        f"define the potential action<{_MAIN_FQUN_NAME}:/middle> {{\n"
        f"    define the position<_noop>.\n"
        f"    it happens when {{\n"
        f"        the position<_noop> has a particle.\n"
        f"    }} and it does {{\n"
        f"        define the position<__noop>.\n"
        f"        create a particle in position<__noop>.\n"
        f"    }}\n"
        f"}}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/outer> {{\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</middle>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<iface>::action</middle>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_MAIN_FQUN_NAME}:/outer>",
)

_MIDDLE = _parse_action(
    (
        f"define the potential action<{_MAIN_FQUN_NAME}:/inner> {{\n"
        f"    define the position<_noop>.\n"
        f"    it happens when {{\n"
        f"        the position<_noop> has a particle.\n"
        f"    }} and it does {{\n"
        f"        define the position<__noop>.\n"
        f"        create a particle in position<__noop>.\n"
        f"    }}\n"
        f"}}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/middle> {{\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<mid_iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</inner>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_MAIN_FQUN_NAME}:/middle>",
)

_INNER = _parse_action(
    (
        f"define the potential position<{_DEP_FQUN_NAME}:/x>.\n"
        f"define the potential action<{_DEP_FQUN_NAME}:/inner> {{\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<item> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</x>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<item>::position</x>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_DEP_FQUN_NAME}:/inner>",
)

_COMPLEX_CHAIN = _parse_action(
    (
        f"define the potential position<{_MAIN_FQUN_NAME}:/x>.\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/foo> {{\n"
        "    define the position<iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</x>.\n"
        "        }\n"
        "    }\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<iface>::position</x>.\n"
        "    }\n"
        "}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/bar> {{\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/test> {{\n"
        "    define the position<run>.\n"
        "    define the position<local> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</x>.\n"
        "            it has the action</foo>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<local>::position</x>::action</foo>::position<iface>::position</x>::action</bar>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
)

_MAIN_IMPLIES_POSITION = _parse_action(
    (
        f"define the potential position<{_MAIN_FQUN_NAME}:/x>.\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/main_implies> {{\n"
        "    it also assigns the position</x>.\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position</x>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_MAIN_FQUN_NAME}:/main_implies>",
)

_DEP_IMPLIES_POSITION = _parse_action(
    (
        f"define the potential position<{_DEP_FQUN_NAME}:/x>.\n"
        f"define the potential action<{_DEP_FQUN_NAME}:/dep_implies> {{\n"
        "    it also assigns the position</x>.\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position</x>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_DEP_FQUN_NAME}:/dep_implies>",
)

_MAIN_FQUN = _get_fqun(_OUTER)
_DEP_FQUN = _get_fqun(_INNER)


class TestRootCauseActionName:
    def test_non_propagated(self):
        req = _direct_requirement(_OUTER)
        assert req.root_cause_action_name() == f"action<{_MAIN_FQUN_NAME}:/outer>"

    def test_single_propagation(self):
        leaf = _direct_requirement(_INNER)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF), _OUTER
        )
        assert propagated.root_cause_action_name() == f"action<{_DEP_FQUN_NAME}:/inner>"

    def test_double_propagation(self):
        leaf = _direct_requirement(_INNER)
        middle = _propagated_requirement(
            leaf, _make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF), _MIDDLE
        )
        outer = _propagated_requirement(
            middle, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert outer.root_cause_action_name() == f"action<{_DEP_FQUN_NAME}:/inner>"

    def test_implied_position_propagation(self):
        leaf = _direct_requirement(_MAIN_IMPLIES_POSITION)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert propagated.required_state == _EMPTY
        assert (
            propagated.position.source_chained_name == "position<iface>::position</x>"
        )
        assert propagated.enclosing_action is _OUTER
        assert propagated.propagated_from is leaf
        assert leaf.required_state == _EMPTY
        assert leaf.position.source_chained_name == "position</x>"
        assert leaf.enclosing_action is _MAIN_IMPLIES_POSITION
        assert leaf.propagated_from is None
        assert (
            propagated.root_cause_action_name()
            == f"action<{_MAIN_FQUN_NAME}:/main_implies>"
        )


class TestResolvedChainedName:
    def test_non_propagated_same_fqun(self):
        req = _direct_requirement(_OUTER)
        assert (
            _resolved(req, _MAIN_FQUN)
            == "position<iface>::action</middle>::position<trigger_pos>"
        )

    def test_non_propagated_with_global_ref_same_fqun(self):
        req = _direct_requirement(_INNER)
        assert _resolved(req, _DEP_FQUN) == "position<item>::position</x>"

    def test_non_propagated_cross_fqun(self):
        req = _direct_requirement(_INNER)
        assert (
            _resolved(req, _MAIN_FQUN)
            == f"position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_single_propagation_same_fqun(self):
        leaf = _direct_requirement(_MIDDLE)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert _resolved(propagated, _MAIN_FQUN) == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>::position<trigger_pos>"
        )

    def test_single_propagation_cross_fqun(self):
        leaf = _direct_requirement(_INNER)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF), _OUTER
        )
        assert _resolved(propagated, _MAIN_FQUN) == (
            f"position<iface>::action</inner>"
            f"::position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_double_propagation_mixed_fqun(self):
        leaf = _direct_requirement(_INNER)
        middle = _propagated_requirement(
            leaf, _make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF), _MIDDLE
        )
        outer = _propagated_requirement(
            middle, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert _resolved(outer, _MAIN_FQUN) == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>"
            f"::position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_complex_chain_same_fqun(self):
        req = _direct_requirement(_COMPLEX_CHAIN)
        assert _resolved(req, _MAIN_FQUN) == (
            "position<local>"
            "::position</x>"
            "::action</foo>"
            "::position<iface>"
            "::position</x>"
            "::action</bar>"
            "::position<trigger_pos>"
        )

    def test_implied_position_non_propagated_same_fqun(self):
        req = _direct_requirement(_MAIN_IMPLIES_POSITION)
        assert _resolved(req, _MAIN_FQUN) == "position</x>"

    def test_implied_position_non_propagated_cross_fqun(self):
        req = _direct_requirement(_DEP_IMPLIES_POSITION)
        assert _resolved(req, _MAIN_FQUN) == f"position<{_DEP_FQUN_NAME}:/x>"

    def test_implied_position_propagation_same_fqun(self):
        # When an implied-position requirement propagates to a caller, the
        # caller-side prefix is just the interface position (no action
        # segment), since the implied quality lives on the same particle as the
        # interface position.
        leaf = _direct_requirement(_MAIN_IMPLIES_POSITION)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert _resolved(propagated, _MAIN_FQUN) == "position<iface>::position</x>"

    def test_implied_position_propagation_cross_fqun(self):
        leaf = _direct_requirement(_DEP_IMPLIES_POSITION)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert _resolved(propagated, _MAIN_FQUN) == (
            f"position<iface>::position<{_DEP_FQUN_NAME}:/x>"
        )


def _make_chain(
    location_from: ast.ASTNode,
    *typed_names: ast.TypedNameReference,
) -> ast.ChainedName:
    return ast.ChainedName(
        location=location_from.location,
        typed_names=typed_names,
    )


def _direct_requirement(
    action: ast.ActionDefinition,
) -> action_contract.PositionRequirement:
    """Build the requirement ``action``'s first create statement imposes directly."""
    create_target = _get_create_ref(action)
    return action_contract.PositionRequirement(
        required_state=_EMPTY,
        position=create_target,
        inferred_at=create_target.location,
        enclosing_action=action,
    )


def _propagated_requirement(
    inner: action_contract.PositionRequirement,
    caller_path: ast.ChainedName,
    enclosing_action: ast.ActionDefinition,
) -> action_contract.PositionRequirement:
    """Build ``inner`` propagated through ``caller_path``, as _record_requirement does."""
    return action_contract.PositionRequirement(
        required_state=inner.required_state,
        position=inner.position.in_caller(caller_path),
        inferred_at=caller_path.location,
        enclosing_action=enclosing_action,
        propagated_from=inner,
    )


# Extract typed name references from the parsed action create targets.
# _OUTER creates: position<iface>::action</middle>::position<trigger_pos>
_OUTER_REF = _get_create_ref(_OUTER)
_IFACE_REF = _OUTER_REF.typed_names[0]
_ACTION_MIDDLE_REF = _OUTER_REF.typed_names[1]

# _MIDDLE creates: position<mid_iface>::action</inner>::position<trigger_pos>
_MIDDLE_REF = _get_create_ref(_MIDDLE)
_MID_IFACE_REF = _MIDDLE_REF.typed_names[0]
_ACTION_INNER_REF = _MIDDLE_REF.typed_names[1]

# _INNER creates: position<item>::position</x>
_INNER_REF = _get_create_ref(_INNER)


class TestPropagationChainChainedName:
    def test_non_propagated(self):
        req = _direct_requirement(_OUTER)
        assert (
            req.position.source_chained_name
            == "position<iface>::action</middle>::position<trigger_pos>"
        )

    def test_single_propagation(self):
        leaf = _direct_requirement(_INNER)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF), _OUTER
        )
        assert (
            propagated.position.source_chained_name
            == "position<iface>::action</inner>::position<item>::position</x>"
        )

    def test_double_propagation(self):
        leaf = _direct_requirement(_INNER)
        middle = _propagated_requirement(
            leaf, _make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF), _MIDDLE
        )
        outer = _propagated_requirement(
            middle, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert outer.position.source_chained_name == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>"
            "::position<item>::position</x>"
        )

    def test_implied_position_non_propagated(self):
        req = _direct_requirement(_MAIN_IMPLIES_POSITION)
        assert req.position.source_chained_name == "position</x>"

    def test_implied_position_propagated(self):
        leaf = _direct_requirement(_MAIN_IMPLIES_POSITION)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert (
            propagated.position.source_chained_name == "position<iface>::position</x>"
        )


class TestPropagatedFromLocations:
    def test_non_propagated(self):
        req = _direct_requirement(_OUTER)
        assert req.propagated_from_locations() == []

    def test_single_propagation(self):
        leaf = _direct_requirement(_INNER)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF), _OUTER
        )
        locs = propagated.propagated_from_locations()
        assert len(locs) == 1
        assert locs[0].line == _get_create_ref(_INNER).location.line

    def test_double_propagation(self):
        leaf = _direct_requirement(_INNER)
        middle = _propagated_requirement(
            leaf, _make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF), _MIDDLE
        )
        outer = _propagated_requirement(
            middle, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        locs = outer.propagated_from_locations()
        assert len(locs) == 2
        assert locs[0].line == _get_create_ref(_MIDDLE).location.line
        assert locs[1].line == _get_create_ref(_INNER).location.line

    def test_implied_position_propagation(self):
        leaf = _direct_requirement(_MAIN_IMPLIES_POSITION)
        propagated = _propagated_requirement(
            leaf, _make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF), _OUTER
        )
        assert propagated.required_state == _EMPTY
        assert (
            propagated.position.source_chained_name == "position<iface>::position</x>"
        )
        assert propagated.enclosing_action is _OUTER
        assert propagated.propagated_from is leaf
        assert leaf.required_state == _EMPTY
        assert leaf.position.source_chained_name == "position</x>"
        assert leaf.enclosing_action is _MAIN_IMPLIES_POSITION
        assert leaf.propagated_from is None
        locs = propagated.propagated_from_locations()
        assert len(locs) == 1
        assert locs[0].line == _get_create_ref(_MAIN_IMPLIES_POSITION).location.line
