# pyright: reportUnusedCallResult=false

import typing

from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors


def _get_contract(
    source: str,
    action_name: str = "action<my.domain.com:my_lib:/test>",
) -> action_contract.ActionContract:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)
    definition_result = result.definition_results[action_name]
    validator = definition_postorder_validator.create_postorder_validator(
        definition_result, result.definition_results, {}, {}
    )
    result = validator.analyze()
    contract = result.contract
    if contract is None:
        raise ValueError(f"No contract for {action_name}")
    return typing.cast("action_contract.ActionContract", contract)


class TestRequirementInference:
    def test_create_target_infers_empty(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert ("position<item>",) in contract.requirements
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )
        assert (
            contract.requirements[("position<item>",)].inferred_from.location.line == 7
        )

    def test_move_source_infers_occupied(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )

    def test_move_destination_infers_empty(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert (
            contract.requirements[("position<dest>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_trigger_positions_excluded(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert ("position<run>",) not in contract.requirements
        assert contract.trigger_position_name == "position<run>"

    def test_first_reference_wins(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<other>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "        move the dimension point in position<item> to position<other>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_local_only_positions_excluded(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<local_only>.\n"
            "        create a dimension point in position<local_only>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert ("position<local_only>",) not in contract.requirements

    def test_no_body_returns_empty_contract(self):
        source = "define the potential action<my.domain.com:my_lib:/test>.\n"
        contract = _get_contract(source)
        assert contract.requirements == {}
        assert contract.guarantees == {}


class TestGuaranteeGeneration:
    def test_created_position_occupied_at_end(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<item>",)]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 37
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_moved_away_position_empty_at_end(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "        move the dimension point in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<item>",)]
        assert isinstance(guarantee, action_contract.EmptyGuarantee)
        assert guarantee.caused_by is not None
        assert guarantee.caused_by.location.line == 9
        assert guarantee.caused_by.location.column == 37
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_trigger_position_retains_origin(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<run>",)]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.source_chained_name == "position<run>"
        assert guarantee.caused_by.location.line == 4
        assert guarantee.caused_by.location.column == 13
        assert guarantee.caused_by.source_chained_name == "position<run>"

    def test_created_dp_is_new(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<item>",)]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 37
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_origin_preserved_through_moves(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<a>.\n"
            "    define the position<b>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<a> to position<b>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<b>",)]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.source_chained_name == "position<a>"
        assert guarantee.caused_by.location.line == 8
        assert guarantee.caused_by.location.column == 52
        assert guarantee.caused_by.source_chained_name == "position<b>"

    def test_swap_origins(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<a>.\n"
            "    define the position<b>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<temp>.\n"
            "        move the dimension point in position<a> to position<temp>.\n"
            "        move the dimension point in position<b> to position<a>.\n"
            "        move the dimension point in position<temp> to position<b>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee_a = contract.guarantees[("position<a>",)]
        assert isinstance(guarantee_a, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_a.origin_position.source_chained_name == "position<b>"
        assert guarantee_a.caused_by.location.line == 10
        assert guarantee_a.caused_by.location.column == 52
        assert guarantee_a.caused_by.source_chained_name == "position<a>"
        guarantee_b = contract.guarantees[("position<b>",)]
        assert isinstance(guarantee_b, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_b.origin_position.source_chained_name == "position<a>"
        assert guarantee_b.caused_by.location.line == 11
        assert guarantee_b.caused_by.location.column == 55
        assert guarantee_b.caused_by.source_chained_name == "position<b>"

    def test_new_dp_qualities(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        guarantee = contract.guarantees[("position<item>",)]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 37


class TestChainedRequirementInference:
    def test_create_at_chain_infers_chain_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert chain_key in contract.requirements
        assert (
            contract.requirements[chain_key].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_move_source_chain_infers_chain_occupied(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert chain_key in contract.requirements
        assert (
            contract.requirements[chain_key].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )

    def test_move_source_chain_infers_first_element_occupied(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert ("position<item>",) in contract.requirements
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )

    def test_move_dest_chain_infers_chain_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<src>.\n"
            "    define the position<dest> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<src> to position<dest>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<dest>", "position<my.domain.com:my_lib:/x>")
        assert chain_key in contract.requirements
        assert (
            contract.requirements[chain_key].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_chain_requirement_has_source_name(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert (
            contract.requirements[chain_key].inferred_from.source_chained_name
            == "position<item>::position</x>"
        )


class TestChainedGuaranteeGeneration:
    def test_create_at_chain_generates_occupied_guarantee(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        guarantee = contract.guarantees[chain_key]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 12
        assert guarantee.caused_by.location.column == 37
        assert guarantee.caused_by.source_chained_name == "position<item>::position</x>"

    def test_move_away_from_chain_generates_empty_guarantee(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        guarantee = contract.guarantees[chain_key]
        assert isinstance(guarantee, action_contract.EmptyGuarantee)
        assert guarantee.caused_by is not None
        assert guarantee.caused_by.location.line == 13
        assert guarantee.caused_by.location.column == 37
        assert guarantee.caused_by.source_chained_name == "position<item>::position</x>"

    def test_move_to_chain_generates_occupied_guarantee(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<src>.\n"
            "    define the position<dest> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<src> to position<dest>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<dest>", "position<my.domain.com:my_lib:/x>")
        guarantee = contract.guarantees[chain_key]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.source_chained_name == "position<src>"
        assert guarantee.caused_by.location.line == 13
        assert guarantee.caused_by.location.column == 54
        assert guarantee.caused_by.source_chained_name == "position<dest>::position</x>"

    def test_move_from_chain_away_and_back_preserves_existing_origin(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<tmp>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<item>::position</x> to position<tmp>.\n"
            "        move the dimension point in position<tmp> to position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        guarantee = contract.guarantees[chain_key]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert (
            guarantee.origin_position.source_chained_name
            == "position<item>::position</x>"
        )
        assert guarantee.caused_by.location.line == 14
        assert guarantee.caused_by.location.column == 54
        assert guarantee.caused_by.source_chained_name == "position<item>::position</x>"

    def test_chain_guarantee_qualities(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        guarantee = contract.guarantees[chain_key]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 12
        assert guarantee.caused_by.location.column == 37


_POS_TEST = "position<my.domain.com:my_lib:/test>"
_POS_DEP = "position<my.domain.com:my_lib:/dep>"


def _get_position_contract(
    source: str,
    position_name: str = _POS_TEST,
) -> action_contract.PositionInitBlockContract:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)
    definition_result = result.definition_results[position_name]
    validator = definition_postorder_validator.create_postorder_validator(
        definition_result, result.definition_results, {}, {}
    )
    result = validator.analyze()
    contract = result.contract
    if contract is None:
        raise ValueError(f"No contract for {position_name}")
    return typing.cast("action_contract.PositionInitBlockContract", contract)


class TestPositionInitBlockContract:
    def test_no_init_block_returns_no_contract(self):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        result = program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
        assert_no_errors(result)
        definition_result = result.definition_results[_POS_TEST]
        validator = definition_postorder_validator.create_postorder_validator(
            definition_result, result.definition_results, {}, {}
        )
        result = validator.analyze()
        assert result.contract is None

    def test_init_block_creates_in_self(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        create a dimension point in position</test>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_position_contract(source)
        assert set(contract.guarantees.keys()) == {(_POS_TEST,)}
        guarantee = contract.guarantees[(_POS_TEST,)]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
        assert guarantee.caused_by.location.line == 3
        assert guarantee.caused_by.location.column == 37

    def test_local_only_produces_empty_guarantees(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        define the position<local>.\n"
            "        create a dimension point in position<local>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_position_contract(source)
        assert contract.guarantees == {}

    def test_init_block_with_constraint_child(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</dep>.\n"
            "    }\n"
            "    after it is assigned {\n"
            "        create a dimension point in position</test>.\n"
            "        create a dimension point in position</test>::position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_position_contract(source)
        assert set(contract.guarantees.keys()) == {
            (_POS_TEST,),
            (_POS_TEST, _POS_DEP),
        }
        self_guarantee = contract.guarantees[(_POS_TEST,)]
        assert isinstance(self_guarantee, action_contract.OccupiedByNewGuarantee)
        assert self_guarantee.qualities == frozenset({_POS_DEP})
        assert self_guarantee.caused_by.location.line == 7
        dep_guarantee = contract.guarantees[(_POS_TEST, _POS_DEP)]
        assert isinstance(dep_guarantee, action_contract.OccupiedByNewGuarantee)
        assert dep_guarantee.qualities == frozenset()
        assert dep_guarantee.caused_by.location.line == 8
