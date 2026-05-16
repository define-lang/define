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
    definition = result.definition_results[action_name].definition
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
        if isinstance(stmt, ast.CreateDimensionPointStatement)
    ]
    return creates[index].target_position


def _resolved(req: action_contract.PositionRequirement, fqun: ast.Fqun) -> str:
    return req.full_propagation_position_chain().source_form_in_universe(fqun)


_EMPTY = action_contract.PositionOccupancyState.EMPTY

_OUTER = _parse_action(
    (
        f"define the potential action<{_MAIN_FQUN_NAME}:/middle> {{\n"
        f"    define the position<_noop>.\n"
        f"    it happens when {{\n"
        f"        the position<_noop> has a dimension point.\n"
        f"    }} and it does {{\n"
        f"        define the position<__noop>.\n"
        f"        create a dimension point in position<__noop>.\n"
        f"    }}\n"
        f"}}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/outer> {{\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<iface> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the action</middle>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<iface>::action</middle>::position<trigger_pos>.\n"
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
        f"        the position<_noop> has a dimension point.\n"
        f"    }} and it does {{\n"
        f"        define the position<__noop>.\n"
        f"        create a dimension point in position<__noop>.\n"
        f"    }}\n"
        f"}}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/middle> {{\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<mid_iface> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the action</inner>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
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
        "        it may only contain dimension points where {\n"
        "            it has the position</x>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<item>::position</x>.\n"
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
        "        it may only contain dimension points where {\n"
        "            it has the position</x>.\n"
        "        }\n"
        "    }\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/bar> {{\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
        f"define the potential action<{_MAIN_FQUN_NAME}:/test> {{\n"
        "    define the position<run>.\n"
        "    define the position<local> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</x>.\n"
        "            it has the action</foo>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::position</x>::action</bar>::position<trigger_pos>.\n"
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
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position</x>.\n"
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
        "        the position<trigger_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position</x>.\n"
        "    }\n"
        "}\n"
    ),
    action_name=f"action<{_DEP_FQUN_NAME}:/dep_implies>",
)

_MAIN_FQUN = _get_fqun(_OUTER)
_DEP_FQUN = _get_fqun(_INNER)


class TestRootCauseActionName:
    def test_non_propagated(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_OUTER),
            enclosing_quality=_OUTER,
        )
        assert req.root_cause_quality_name() == f"action<{_MAIN_FQUN_NAME}:/outer>"

    def test_single_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert (
            propagated.root_cause_quality_name() == f"action<{_DEP_FQUN_NAME}:/inner>"
        )

    def test_double_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        middle = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_MIDDLE,
            propagated_from=leaf,
        )
        outer = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=middle,
        )
        assert outer.root_cause_quality_name() == f"action<{_DEP_FQUN_NAME}:/inner>"

    def test_implied_position_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert propagated.required_state == _EMPTY
        assert (
            propagated.inferred_from.source_chained_name
            == "position<iface>::action</middle>"
        )
        assert propagated.enclosing_quality is _OUTER
        assert propagated.propagated_from is leaf
        assert leaf.required_state == _EMPTY
        assert leaf.inferred_from.source_chained_name == "position</x>"
        assert leaf.enclosing_quality is _MAIN_IMPLIES_POSITION
        assert leaf.propagated_from is None
        assert (
            propagated.root_cause_quality_name()
            == f"action<{_MAIN_FQUN_NAME}:/main_implies>"
        )


class TestResolvedChainedName:
    def test_non_propagated_same_fqun(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_OUTER),
            enclosing_quality=_OUTER,
        )
        assert (
            _resolved(req, _MAIN_FQUN)
            == "position<iface>::action</middle>::position<trigger_pos>"
        )

    def test_non_propagated_with_global_ref_same_fqun(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        assert _resolved(req, _DEP_FQUN) == "position<item>::position</x>"

    def test_non_propagated_cross_fqun(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        assert (
            _resolved(req, _MAIN_FQUN)
            == f"position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_single_propagation_same_fqun(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MIDDLE),
            enclosing_quality=_MIDDLE,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert _resolved(propagated, _MAIN_FQUN) == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>::position<trigger_pos>"
        )

    def test_single_propagation_cross_fqun(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert _resolved(propagated, _MAIN_FQUN) == (
            f"position<iface>::action</inner>"
            f"::position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_double_propagation_mixed_fqun(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        middle = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_MIDDLE,
            propagated_from=leaf,
        )
        outer = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=middle,
        )
        assert _resolved(outer, _MAIN_FQUN) == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>"
            f"::position<item>::position<{_DEP_FQUN_NAME}:/x>"
        )

    def test_complex_chain_same_fqun(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_COMPLEX_CHAIN),
            enclosing_quality=_COMPLEX_CHAIN,
        )
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
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        assert _resolved(req, _MAIN_FQUN) == "position</x>"

    def test_implied_position_non_propagated_cross_fqun(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_DEP_IMPLIES_POSITION),
            enclosing_quality=_DEP_IMPLIES_POSITION,
        )
        assert _resolved(req, _MAIN_FQUN) == f"position<{_DEP_FQUN_NAME}:/x>"

    def test_implied_position_propagation_same_fqun(self):
        # When an implied-position requirement propagates to a caller, the
        # caller-side prefix is just the interface position (no action
        # segment), since the implied quality lives on the same DP as the
        # interface position.
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert _resolved(propagated, _MAIN_FQUN) == "position<iface>::position</x>"

    def test_implied_position_propagation_cross_fqun(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_DEP_IMPLIES_POSITION),
            enclosing_quality=_DEP_IMPLIES_POSITION,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
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
        typed_names=list(typed_names),
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
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_OUTER),
            enclosing_quality=_OUTER,
        )
        assert (
            req.full_propagation_position_chain().source_chained_name
            == "position<iface>::action</middle>::position<trigger_pos>"
        )

    def test_single_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert (
            propagated.full_propagation_position_chain().source_chained_name
            == "position<iface>::action</inner>::position<item>::position</x>"
        )

    def test_double_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        middle = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_MIDDLE,
            propagated_from=leaf,
        )
        outer = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=middle,
        )
        assert outer.full_propagation_position_chain().source_chained_name == (
            "position<iface>::action</middle>"
            "::position<mid_iface>::action</inner>"
            "::position<item>::position</x>"
        )

    def test_implied_position_non_propagated(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        assert (
            req.full_propagation_position_chain().source_chained_name == "position</x>"
        )

    def test_implied_position_propagated(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert (
            propagated.full_propagation_position_chain().source_chained_name
            == "position<iface>::position</x>"
        )


class TestPropagatedFromLocations:
    def test_non_propagated(self):
        req = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_OUTER),
            enclosing_quality=_OUTER,
        )
        assert req.propagated_from_locations() == []

    def test_single_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        locs = propagated.propagated_from_locations()
        assert len(locs) == 1
        assert locs[0].line == _get_create_ref(_INNER).location.line

    def test_double_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_INNER),
            enclosing_quality=_INNER,
        )
        middle = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_MIDDLE_REF, _MID_IFACE_REF, _ACTION_INNER_REF),
            enclosing_quality=_MIDDLE,
            propagated_from=leaf,
        )
        outer = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=middle,
        )
        locs = outer.propagated_from_locations()
        assert len(locs) == 2
        assert locs[0].line == _get_create_ref(_MIDDLE).location.line
        assert locs[1].line == _get_create_ref(_INNER).location.line

    def test_implied_position_propagation(self):
        leaf = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_get_create_ref(_MAIN_IMPLIES_POSITION),
            enclosing_quality=_MAIN_IMPLIES_POSITION,
        )
        propagated = action_contract.PositionRequirement(
            required_state=_EMPTY,
            inferred_from=_make_chain(_OUTER_REF, _IFACE_REF, _ACTION_MIDDLE_REF),
            enclosing_quality=_OUTER,
            propagated_from=leaf,
        )
        assert propagated.required_state == _EMPTY
        assert (
            propagated.inferred_from.source_chained_name
            == "position<iface>::action</middle>"
        )
        assert propagated.enclosing_quality is _OUTER
        assert propagated.propagated_from is leaf
        assert leaf.required_state == _EMPTY
        assert leaf.inferred_from.source_chained_name == "position</x>"
        assert leaf.enclosing_quality is _MAIN_IMPLIES_POSITION
        assert leaf.propagated_from is None
        locs = propagated.propagated_from_locations()
        assert len(locs) == 1
        assert locs[0].line == _get_create_ref(_MAIN_IMPLIES_POSITION).location.line
