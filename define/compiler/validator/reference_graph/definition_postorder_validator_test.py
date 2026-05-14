# pyright: reportUnusedCallResult=false

import typing
import unittest.mock
from pathlib import PurePosixPath

from define.compiler import ast, conftest
from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors


def _resolved(req: action_contract.PositionRequirement, fqun: ast.Fqun) -> str:
    return req.full_propagation_position_chain().source_form_in_universe(fqun)


def _assert_trigger_guarantee(
    entry: action_contract.GuaranteePair, line: int, column: int = 13
):
    key, guarantee = entry
    assert key == ("position<run>",)
    assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
    assert guarantee.origin_position.source_chained_name == "position<run>"
    assert guarantee.caused_by.location.line == line
    assert guarantee.caused_by.location.column == column
    assert guarantee.caused_by.source_chained_name == "position<run>"


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

    def test_local_only_chain_via_constraints_excluded(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/grandchild>.\n"
            "define the potential position<my.domain.com:my_lib:/child> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</grandchild>.\n"
            "    }\n"
            "}\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<container> {\n"
            "            it may only contain dimension points where {\n"
            "                it has the position</child>.\n"
            "            }\n"
            "        }\n"
            "        create a dimension point in position<container>.\n"
            "        create a dimension point in position<container>::position</child>.\n"
            "        create a dimension point in position<container>::position</child>::position</grandchild>.\n"
            "        destroy the dimension point in position<container>::position</child>::position</grandchild>.\n"
            "        destroy the dimension point in position<container>::position</child>.\n"
            "        destroy the dimension point in position<container>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        assert contract.requirements == {}


_IMPLIED_POSITION = "position<my.domain.com:my_lib:/implied>"
_IMPLIED_ACTION = "action<my.domain.com:my_lib:/sub>"
_SUB_IFACE = "position<iface>"


class TestImpliedPositionRequirementInference:
    def test_create_in_implied_position_infers_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/implied>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</implied>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position</implied>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        key = (_IMPLIED_POSITION,)
        assert key in contract.requirements
        req = contract.requirements[key]
        assert req.required_state == action_contract.PositionOccupancyState.EMPTY
        assert req.inferred_from.source_chained_name == "position</implied>"
        assert req.inferred_from.location.line == 8

    def test_destroy_in_implied_position_infers_occupied(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/implied>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</implied>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        destroy the dimension point in position</implied>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        key = (_IMPLIED_POSITION,)
        assert key in contract.requirements
        assert (
            contract.requirements[key].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )

    def test_create_in_implied_action_iface_infers_empty(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/sub> {\n"
            "    define the position<iface>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the action</sub>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</sub>::position<iface>.\n"
            "    }\n"
            "}\n"
        )
        contract = _get_contract(source)
        leaf_key = (_IMPLIED_ACTION, _SUB_IFACE)
        assert leaf_key in contract.requirements
        leaf = contract.requirements[leaf_key]
        assert leaf.required_state == action_contract.PositionOccupancyState.EMPTY
        assert leaf.inferred_from.source_chained_name == "action</sub>::position<iface>"


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
        assert len(contract.guarantees) == 2
        _assert_trigger_guarantee(contract.guarantees[0], line=5)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee = contract.guarantees[1][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert len(contract.guarantees) == 3
        _assert_trigger_guarantee(contract.guarantees[0], line=6)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee_item = contract.guarantees[1][1]
        assert isinstance(guarantee_item, action_contract.EmptyGuarantee)
        assert guarantee_item.caused_by.location.line == 9
        assert guarantee_item.caused_by.location.column == 37
        assert guarantee_item.caused_by.source_chained_name == "position<item>"
        assert contract.guarantees[2][0] == ("position<dest>",)
        guarantee_dest = contract.guarantees[2][1]
        assert isinstance(guarantee_dest, action_contract.OccupiedByNewGuarantee)
        assert guarantee_dest.qualities == []
        assert guarantee_dest.caused_by.location.line == 9
        assert guarantee_dest.caused_by.location.column == 55
        assert guarantee_dest.caused_by.source_chained_name == "position<dest>"

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
        assert len(contract.guarantees) == 1
        _assert_trigger_guarantee(contract.guarantees[0], line=4)

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
        assert len(contract.guarantees) == 2
        _assert_trigger_guarantee(contract.guarantees[0], line=5)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee = contract.guarantees[1][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert len(contract.guarantees) == 3
        _assert_trigger_guarantee(contract.guarantees[0], line=6)
        assert contract.guarantees[1][0] == ("position<a>",)
        guarantee_a = contract.guarantees[1][1]
        assert isinstance(guarantee_a, action_contract.EmptyGuarantee)
        assert guarantee_a.caused_by.location.line == 8
        assert guarantee_a.caused_by.location.column == 37
        assert guarantee_a.caused_by.source_chained_name == "position<a>"
        assert contract.guarantees[2][0] == ("position<b>",)
        guarantee_b = contract.guarantees[2][1]
        assert isinstance(guarantee_b, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_b.origin_position.source_chained_name == "position<a>"
        assert guarantee_b.caused_by.location.line == 8
        assert guarantee_b.caused_by.location.column == 52
        assert guarantee_b.caused_by.source_chained_name == "position<b>"

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
        assert len(contract.guarantees) == 3
        _assert_trigger_guarantee(contract.guarantees[0], line=6)
        assert contract.guarantees[1][0] == ("position<a>",)
        guarantee_a = contract.guarantees[1][1]
        assert isinstance(guarantee_a, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_a.origin_position.source_chained_name == "position<b>"
        assert guarantee_a.caused_by.location.line == 10
        assert guarantee_a.caused_by.location.column == 52
        assert guarantee_a.caused_by.source_chained_name == "position<a>"
        assert contract.guarantees[2][0] == ("position<b>",)
        guarantee_b = contract.guarantees[2][1]
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
        assert len(contract.guarantees) == 2
        _assert_trigger_guarantee(contract.guarantees[0], line=5)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee = contract.guarantees[1][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert len(contract.guarantees) == 3
        _assert_trigger_guarantee(contract.guarantees[0], line=10)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee_item = contract.guarantees[1][1]
        assert isinstance(guarantee_item, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_item.origin_position.source_chained_name == "position<item>"
        assert guarantee_item.caused_by.location.line == 12
        assert guarantee_item.caused_by.location.column == 37
        assert guarantee_item.caused_by.source_chained_name == "position<item>"
        assert contract.guarantees[2][0] == chain_key
        guarantee = contract.guarantees[2][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert len(contract.guarantees) == 4
        _assert_trigger_guarantee(contract.guarantees[0], line=11)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee_item = contract.guarantees[1][1]
        assert isinstance(guarantee_item, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_item.origin_position.source_chained_name == "position<item>"
        assert guarantee_item.caused_by.location.line == 13
        assert guarantee_item.caused_by.location.column == 37
        assert guarantee_item.caused_by.source_chained_name == "position<item>"
        assert contract.guarantees[2][0] == ("position<dest>",)
        guarantee_dest = contract.guarantees[2][1]
        assert isinstance(guarantee_dest, action_contract.OccupiedByExistingGuarantee)
        assert (
            guarantee_dest.origin_position.source_chained_name
            == "position<item>::position</x>"
        )
        assert guarantee_dest.caused_by.location.line == 13
        assert guarantee_dest.caused_by.location.column == 69
        assert guarantee_dest.caused_by.source_chained_name == "position<dest>"
        assert contract.guarantees[3][0] == chain_key
        guarantee = contract.guarantees[3][1]
        assert isinstance(guarantee, action_contract.EmptyGuarantee)
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
        assert len(contract.guarantees) == 4
        _assert_trigger_guarantee(contract.guarantees[0], line=11)
        assert contract.guarantees[1][0] == ("position<src>",)
        guarantee_src = contract.guarantees[1][1]
        assert isinstance(guarantee_src, action_contract.EmptyGuarantee)
        assert guarantee_src.caused_by.location.line == 13
        assert guarantee_src.caused_by.location.column == 37
        assert guarantee_src.caused_by.source_chained_name == "position<src>"
        assert contract.guarantees[2][0] == ("position<dest>",)
        guarantee_dest = contract.guarantees[2][1]
        assert isinstance(guarantee_dest, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_dest.origin_position.source_chained_name == "position<dest>"
        assert guarantee_dest.caused_by.location.line == 13
        assert guarantee_dest.caused_by.location.column == 54
        assert guarantee_dest.caused_by.source_chained_name == "position<dest>"
        assert contract.guarantees[3][0] == chain_key
        guarantee = contract.guarantees[3][1]
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
        assert len(contract.guarantees) == 4
        _assert_trigger_guarantee(contract.guarantees[0], line=11)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee_item = contract.guarantees[1][1]
        assert isinstance(guarantee_item, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_item.origin_position.source_chained_name == "position<item>"
        assert guarantee_item.caused_by.location.line == 13
        assert guarantee_item.caused_by.location.column == 37
        assert guarantee_item.caused_by.source_chained_name == "position<item>"
        assert contract.guarantees[2][0] == ("position<tmp>",)
        guarantee_tmp = contract.guarantees[2][1]
        assert isinstance(guarantee_tmp, action_contract.EmptyGuarantee)
        assert guarantee_tmp.caused_by.location.line == 14
        assert guarantee_tmp.caused_by.location.column == 37
        assert guarantee_tmp.caused_by.source_chained_name == "position<tmp>"
        assert contract.guarantees[3][0] == chain_key
        guarantee = contract.guarantees[3][1]
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
        assert len(contract.guarantees) == 3
        _assert_trigger_guarantee(contract.guarantees[0], line=10)
        assert contract.guarantees[1][0] == ("position<item>",)
        guarantee_item = contract.guarantees[1][1]
        assert isinstance(guarantee_item, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_item.origin_position.source_chained_name == "position<item>"
        assert guarantee_item.caused_by.location.line == 12
        assert guarantee_item.caused_by.location.column == 37
        assert guarantee_item.caused_by.source_chained_name == "position<item>"
        assert contract.guarantees[2][0] == chain_key
        guarantee = contract.guarantees[2][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert len(contract.guarantees) == 1
        assert contract.guarantees[0][0] == (_POS_TEST,)
        guarantee = contract.guarantees[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == []
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
        assert contract.guarantees == []

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
        assert len(contract.guarantees) == 2
        assert contract.guarantees[0][0] == (_POS_TEST,)
        self_guarantee = contract.guarantees[0][1]
        assert isinstance(self_guarantee, action_contract.OccupiedByNewGuarantee)
        assert [q.full_typed_name for q in self_guarantee.qualities] == [_POS_DEP]
        assert self_guarantee.caused_by.location.line == 7
        assert contract.guarantees[1][0] == (_POS_TEST, _POS_DEP)
        dep_guarantee = contract.guarantees[1][1]
        assert isinstance(dep_guarantee, action_contract.OccupiedByNewGuarantee)
        assert dep_guarantee.qualities == []
        assert dep_guarantee.caused_by.location.line == 8


_INNER_ACTION = "action<my.domain.com:my_lib:/inner>"
_MIDDLE_ACTION = "action<my.domain.com:my_lib:/middle>"
_OUTER_ACTION = "action<my.domain.com:my_lib:/outer>"


def test_interface_position_requirement_integration(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    captured_contracts: dict[str, action_contract.ActionContract] = {}
    original_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def spy_analyze(
        validator_self: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        result = original_analyze(validator_self)
        if isinstance(result.contract, action_contract.ActionContract):
            name = validator_self._definition.typed_name.source_typed_name  # pyright: ignore[reportPrivateUsage]
            captured_contracts[name] = result.contract
        return result

    with unittest.mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=spy_analyze,
    ):
        validate_project_with_reference_graph(
            {
                "inner.dfn": (
                    "define the potential action<my.domain.com:my_lib:/inner> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    define the position<item>.\n"
                    "    define the position<dest>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<item> to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "middle.dfn": (
                    "define the potential action<my.domain.com:my_lib:/middle> {\n"
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
                "outer.dfn": (
                    "define the potential action<my.domain.com:my_lib:/outer> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    define the position<out_iface> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</middle>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<out_iface>::action</middle>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
            entry_file="outer.dfn",
        )

    outer_contract = captured_contracts[_OUTER_ACTION]
    req_key = (
        "position<out_iface>",
        "action<my.domain.com:my_lib:/middle>",
        "position<mid_iface>",
        "action<my.domain.com:my_lib:/inner>",
        "position<item>",
    )
    req = outer_contract.requirements[req_key]

    # Fields on the outermost requirement
    assert req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert req.enclosing_action.typed_name.source_typed_name == _OUTER_ACTION
    assert (
        req.inferred_from.source_chained_name == "position<out_iface>::action</middle>"
    )
    assert req.inferred_from.location.line == 11
    assert req.inferred_from.location.file_path == PurePosixPath("outer.dfn")

    # Middle level of propagation chain
    assert req.propagated_from is not None
    mid_req = req.propagated_from
    assert mid_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert mid_req.enclosing_action.typed_name.source_typed_name == _MIDDLE_ACTION
    assert (
        mid_req.inferred_from.source_chained_name
        == "position<mid_iface>::action</inner>"
    )
    assert mid_req.inferred_from.location.line == 11
    assert mid_req.inferred_from.location.file_path == PurePosixPath("middle.dfn")

    # Leaf level — the original requirement from /inner
    assert mid_req.propagated_from is not None
    inner_req = mid_req.propagated_from
    assert inner_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert inner_req.enclosing_action.typed_name.source_typed_name == _INNER_ACTION
    assert inner_req.inferred_from.source_chained_name == "position<item>"
    assert inner_req.inferred_from.location.line == 8
    assert inner_req.inferred_from.location.file_path == PurePosixPath("inner.dfn")
    assert inner_req.propagated_from is None

    # Methods on the outermost requirement
    assert req.root_cause_action_name() == _INNER_ACTION
    outer_fqun = req.enclosing_action.typed_name.name_content.fqun
    assert _resolved(req, outer_fqun) == (
        "position<out_iface>::action</middle>"
        "::position<mid_iface>::action</inner>"
        "::position<item>"
    )
    assert req.full_propagation_position_chain().source_chained_name == (
        "position<out_iface>::action</middle>"
        "::position<mid_iface>::action</inner>::position<item>"
    )
    outer_locs = req.propagated_from_locations()
    assert len(outer_locs) == 2
    assert outer_locs[0].line == 11
    assert outer_locs[0].file_path == PurePosixPath("middle.dfn")
    assert outer_locs[1].line == 8
    assert outer_locs[1].file_path == PurePosixPath("inner.dfn")

    # Methods on the middle requirement
    assert mid_req.root_cause_action_name() == _INNER_ACTION
    middle_fqun = mid_req.enclosing_action.typed_name.name_content.fqun
    assert _resolved(mid_req, middle_fqun) == (
        "position<mid_iface>::action</inner>::position<item>"
    )
    assert mid_req.full_propagation_position_chain().source_chained_name == (
        "position<mid_iface>::action</inner>::position<item>"
    )
    mid_locs = mid_req.propagated_from_locations()
    assert len(mid_locs) == 1
    assert mid_locs[0].line == 8
    assert mid_locs[0].file_path == PurePosixPath("inner.dfn")

    # Methods on the leaf requirement
    assert inner_req.root_cause_action_name() == _INNER_ACTION
    inner_fqun = inner_req.enclosing_action.typed_name.name_content.fqun
    assert _resolved(inner_req, inner_fqun) == "position<item>"
    assert (
        inner_req.full_propagation_position_chain().source_chained_name
        == "position<item>"
    )
    assert inner_req.propagated_from_locations() == []
