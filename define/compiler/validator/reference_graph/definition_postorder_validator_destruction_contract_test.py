# pyright: reportUnusedCallResult=false

from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.test_helpers import get_contracts

_OCCUPIED = action_contract.PositionOccupancyState.OCCUPIED
_EMPTY = action_contract.PositionOccupancyState.EMPTY

_FILE = "define the potential position<my.domain.com:my_lib:/file>.\n"

_DELETE_FILE_DESTRUCTOR = (
    "define the potential action<my.domain.com:my_lib:/delete_file_destructor> {\n"
    "    it also assigns the position</file>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the particle in position</file> to position<_holder>.\n"
    "        move the particle in position<_holder> to position</file>.\n"
    "    }\n"
    "}\n"
)

_NOOP_D1 = (
    "define the potential action<my.domain.com:my_lib:/d1> {\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_x>.\n"
    "        create a particle in position<_x>.\n"
    "    }\n"
    "}\n"
)
_NOOP_D2 = _NOOP_D1.replace("/d1>", "/d2>")

_CLOSE_BLIND = (
    "define the potential action<my.domain.com:my_lib:/close_file> {\n"
    "    define the position<target>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        destroy the particle in position<target>.\n"
    "    }\n"
    "}\n"
)


def _destruction_contracts(source: str, action: str):
    return get_contracts(source)[
        f"action<my.domain.com:my_lib:/{action}>"
    ].destruction_contracts


def _child_states(contract: action_contract.DestructionContract):
    # Occupancy state per child position; fill locations are covered by the
    # tracker snapshot test and the caller-verification diagnostic tests.
    return {key: occupancy.state for key, occupancy in contract.child_state.items()}


def test_owned_particle_records_no_contract():
    source = (
        "define the potential action<my.domain.com:my_lib:/owned_destroy> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<item>.\n"
        "        destroy the particle in position<item>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/owned_auto> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<item>.\n"
        "    }\n"
        "}\n"
    )
    assert _destruction_contracts(source, "owned_destroy") == []
    assert _destruction_contracts(source, "owned_auto") == []


_CLOSER_DIRECT_DESTROY = (
    "define the potential action<my.domain.com:my_lib:/closer> {\n"
    "    define the position<target> {\n"
    "        it may only contain particles where {\n"
    "            it has the position</file>.\n"
    "            it has the action</delete_file_destructor>.\n"
    "        }\n"
    "    }\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<target>::position</file>.\n"
    "        destroy the particle in position<target>.\n"
    "    }\n"
    "}\n"
)


def test_passed_in_direct_destroy_records_contract():
    source = _FILE + _DELETE_FILE_DESTRUCTOR + _CLOSER_DIRECT_DESTROY
    dcs = _destruction_contracts(source, "closer")
    assert len(dcs) == 1
    dc = dcs[0]
    assert dc.destroyed_position_contracted.source_chained_name == "position<target>"
    # Destroyed directly, so local == contracted.
    assert dc.destroyed_position_local.source_chained_name == "position<target>"
    assert dc.is_auto_destruction is False
    assert (
        dc.destroying_action.full_typed_name == "action<my.domain.com:my_lib:/closer>"
    )
    assert [quality.full_typed_name for quality in dc.verified_destructors] == [
        "action<my.domain.com:my_lib:/delete_file_destructor>"
    ]
    assert _child_states(dc) == {("position<my.domain.com:my_lib:/file>",): _OCCUPIED}


def test_moved_in_particle_preserves_contracted_origin():
    source = (
        "define the potential action<my.domain.com:my_lib:/mover> {\n"
        "    define the position<incoming>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box>.\n"
        "        move the particle in position<incoming> to position<box>.\n"
        "        destroy the particle in position<box>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "mover")
    assert len(dcs) == 1
    # Keyed on the contracted origin it came in through, not the local it died in.
    assert (
        dcs[0].destroyed_position_contracted.source_chained_name == "position<incoming>"
    )
    assert dcs[0].destroyed_position_local.source_chained_name == "position<box>"
    assert dcs[0].is_auto_destruction is False


def test_auto_destruction_of_moved_in_particle():
    source = (
        "define the potential action<my.domain.com:my_lib:/autoer> {\n"
        "    define the position<incoming>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box>.\n"
        "        move the particle in position<incoming> to position<box>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "autoer")
    assert len(dcs) == 1
    assert (
        dcs[0].destroyed_position_contracted.source_chained_name == "position<incoming>"
    )
    assert dcs[0].destroyed_position_local.source_chained_name == "position<box>"
    assert dcs[0].is_auto_destruction is True


def test_multiple_destroys_record_in_execution_order():
    source = (
        "define the potential action<my.domain.com:my_lib:/multi> {\n"
        "    define the position<target1>.\n"
        "    define the position<target2>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        destroy the particle in position<target1>.\n"
        "        destroy the particle in position<target2>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "multi")
    assert [dc.destroyed_position_contracted.source_chained_name for dc in dcs] == [
        "position<target1>",
        "position<target2>",
    ]


def test_explicit_then_auto_destruction_in_execution_order():
    source = (
        "define the potential action<my.domain.com:my_lib:/mixed> {\n"
        "    define the position<target>.\n"
        "    define the position<incoming>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box>.\n"
        "        destroy the particle in position<target>.\n"
        "        move the particle in position<incoming> to position<box>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "mixed")
    # Explicit destroy first, then the moved-in particle auto-destroyed at block end.
    assert len(dcs) == 2
    assert (
        dcs[0].destroyed_position_contracted.source_chained_name == "position<target>"
    )
    assert dcs[0].is_auto_destruction is False
    assert (
        dcs[1].destroyed_position_contracted.source_chained_name == "position<incoming>"
    )
    assert dcs[1].is_auto_destruction is True


def test_destroy_implied_position_keys_on_implied_origin():
    source = (
        "define the potential position<my.domain.com:my_lib:/slot>.\n"
        "define the potential action<my.domain.com:my_lib:/implier> {\n"
        "    it also assigns the position</slot>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        destroy the particle in position</slot>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "implier")
    assert len(dcs) == 1
    assert dcs[0].destroyed_position_contracted.source_chained_name == "position</slot>"
    assert dcs[0].destroyed_position_local.source_chained_name == "position</slot>"
    assert dcs[0].is_auto_destruction is False


_CLOSER_TWO_DESTRUCTORS = (
    "define the potential action<my.domain.com:my_lib:/closer> {\n"
    "    define the position<target> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</d1>.\n"
    "            it has the action</d2>.\n"
    "        }\n"
    "    }\n"
    "    define the position<empty_target>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        destroy the particle in position<target>.\n"
    "        destroy the particle in position<empty_target>.\n"
    "    }\n"
    "}\n"
)


def test_verified_destructors_in_firing_order_and_empty_when_none():
    source = _NOOP_D1 + _NOOP_D2 + _CLOSER_TWO_DESTRUCTORS
    dcs = _destruction_contracts(source, "closer")
    assert len(dcs) == 2
    # Firing order is the reverse of declaration order (d1 then d2 declared).
    assert [quality.full_typed_name for quality in dcs[0].verified_destructors] == [
        "action<my.domain.com:my_lib:/d2>",
        "action<my.domain.com:my_lib:/d1>",
    ]
    assert (
        dcs[0].destroyed_position_contracted.source_chained_name == "position<target>"
    )
    assert tuple(dcs[1].verified_destructors) == ()
    assert (
        dcs[1].destroyed_position_contracted.source_chained_name
        == "position<empty_target>"
    )


_SLOT_REQUIRES_FILE = (
    "define the potential position<my.domain.com:my_lib:/slot> {\n"
    "    it may only contain particles where {\n"
    "        it has the position</file>.\n"
    "    }\n"
    "}\n"
)

_CLOSER_CHILD_STATE = (
    "define the potential action<my.domain.com:my_lib:/closer> {\n"
    "    define the position<target> {\n"
    "        it may only contain particles where {\n"
    "            it has the position</file>.\n"
    "            it has the position</slot>.\n"
    "        }\n"
    "    }\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<target>::position</file>.\n"
    "        destroy the particle in position<target>::position</file>.\n"
    "        create a particle in position<target>::position</slot>.\n"
    "        create a particle in position<target>::position</slot>::position</file>.\n"
    "        destroy the particle in position<target>.\n"
    "    }\n"
    "}\n"
)


def test_child_state_captures_occupancy_with_relative_nested_keys():
    source = _FILE + _SLOT_REQUIRES_FILE + _CLOSER_CHILD_STATE
    dcs = _destruction_contracts(source, "closer")
    assert len(dcs) == 1
    # Keys are relative to the destroyed particle, in canonical (full) form.
    assert _child_states(dcs[0]) == {
        ("position<my.domain.com:my_lib:/file>",): _EMPTY,
        ("position<my.domain.com:my_lib:/slot>",): _OCCUPIED,
        (
            "position<my.domain.com:my_lib:/slot>",
            "position<my.domain.com:my_lib:/file>",
        ): _OCCUPIED,
    }


_MID_FILLS_AND_PASSES = (
    "define the potential action<my.domain.com:my_lib:/mid> {\n"
    "    define the position<incoming> {\n"
    "        it may only contain particles where {\n"
    "            it has the position</file>.\n"
    "            it has the action</delete_file_destructor>.\n"
    "        }\n"
    "    }\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        define the position<box> {\n"
    "            it may only contain particles where {\n"
    "                it has the action</close_file>.\n"
    "            }\n"
    "        }\n"
    "        create a particle in position<box>.\n"
    "        create a particle in position<incoming>::position</file>.\n"
    "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
    "        create a particle in position<box>::action</close_file>::position<run>.\n"
    "    }\n"
    "}\n"
)


def test_pass_through_re_records_contract_with_carry_over_and_accumulation():
    source = _FILE + _DELETE_FILE_DESTRUCTOR + _CLOSE_BLIND + _MID_FILLS_AND_PASSES
    dcs = _destruction_contracts(source, "mid")
    assert len(dcs) == 1
    dc = dcs[0]
    # Remapped to how mid received the particle...
    assert dc.destroyed_position_contracted.source_chained_name == "position<incoming>"
    # ...while where/how/who destroyed it carry over unchanged from close_file.
    assert dc.destroyed_position_local.source_chained_name == "position<target>"
    assert (
        dc.destroying_action.full_typed_name
        == "action<my.domain.com:my_lib:/close_file>"
    )
    assert dc.is_auto_destruction is False
    # Cumulative Child State: mid contributed the position</file> it filled.
    assert _child_states(dc) == {("position<my.domain.com:my_lib:/file>",): _OCCUPIED}
    # mid resolved the destructor it knows, so it is added to verified_destructors.
    assert [quality.full_typed_name for quality in dc.verified_destructors] == [
        "action<my.domain.com:my_lib:/delete_file_destructor>"
    ]


_OWNER_CREATES_AND_PASSES = (
    "define the potential action<my.domain.com:my_lib:/owner> {\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a particle.\n"
    "    } and it does {\n"
    "        define the position<box> {\n"
    "            it may only contain particles where {\n"
    "                it has the action</close_file>.\n"
    "            }\n"
    "        }\n"
    "        create a particle in position<box>.\n"
    "        create a particle in position<box>::action</close_file>::position<target>.\n"
    "        create a particle in position<box>::action</close_file>::position<run>.\n"
    "    }\n"
    "}\n"
)


def test_owner_does_not_re_record():
    source = _CLOSE_BLIND + _OWNER_CREATES_AND_PASSES
    assert _destruction_contracts(source, "owner") == []


def test_auto_destructions_record_in_reverse_definition_order():
    source = (
        "define the potential action<my.domain.com:my_lib:/autoer2> {\n"
        "    define the position<incoming1>.\n"
        "    define the position<incoming2>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box1>.\n"
        "        define the position<box2>.\n"
        "        move the particle in position<incoming1> to position<box1>.\n"
        "        move the particle in position<incoming2> to position<box2>.\n"
        "    }\n"
        "}\n"
    )
    dcs = _destruction_contracts(source, "autoer2")
    # Locals auto-destroy in reverse definition order (box2 before box1), so its
    # contract is recorded first.
    assert len(dcs) == 2
    assert (
        dcs[0].destroyed_position_contracted.source_chained_name
        == "position<incoming2>"
    )
    assert dcs[0].destroyed_position_local.source_chained_name == "position<box2>"
    assert dcs[0].is_auto_destruction is True
    assert (
        dcs[1].destroyed_position_contracted.source_chained_name
        == "position<incoming1>"
    )
    assert dcs[1].destroyed_position_local.source_chained_name == "position<box1>"
    assert dcs[1].is_auto_destruction is True
