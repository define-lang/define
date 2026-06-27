# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.test_helpers import (
    get_contracts,
    get_results,
)


def _resolved(req: action_contract.PositionRequirement, fqun: ast.Fqun) -> str:
    return req.full_propagation_position_chain().source_form_in_universe(fqun)


class TestRequirementInference:
    def test_create_target_infers_empty(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert isinstance(contract, action_contract.ActionContract)
        assert ("position<run>",) not in contract.requirements
        assert contract.trigger_position_name == "position<run>"

    def test_first_reference_wins(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<other>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        move the particle in position<item> to position<other>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_local_only_positions_excluded(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<local_only>.\n"
            "        create a particle in position<local_only>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert ("position<local_only>",) not in contract.requirements

    def test_local_only_chain_via_constraints_excluded(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/grandchild>.\n"
            "define the potential position<my.domain.com:my_lib:/child> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</grandchild>.\n"
            "    }\n"
            "}\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<container> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<container>.\n"
            "        create a particle in position<container>::position</child>.\n"
            "        create a particle in position<container>::position</child>::position</grandchild>.\n"
            "        destroy the particle in position<container>::position</child>::position</grandchild>.\n"
            "        destroy the particle in position<container>::position</child>.\n"
            "        destroy the particle in position<container>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert contract.requirements == {}


class TestImpliedPositionRequirementInference:
    def test_create_in_implied_position_infers_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/implied>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</implied>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position</implied>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        key = ("position<my.domain.com:my_lib:/implied>",)
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position</implied>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        key = ("position<my.domain.com:my_lib:/implied>",)
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<iface>.\n"
            "    }\n"
            "}\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the action</sub>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in action</sub>::position<iface>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {
            "action<my.domain.com:my_lib:/sub>",
            "action<my.domain.com:my_lib:/test>",
        }
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        leaf_key = ("action<my.domain.com:my_lib:/sub>", "position<iface>")
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
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == ("position<item>",)
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 30
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_moved_away_position_empty_at_end(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        move the particle in position<item> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == ("position<dest>",)
        guarantee_dest = contract.guarantees.own[0][1]
        assert isinstance(guarantee_dest, action_contract.OccupiedByNewGuarantee)
        assert guarantee_dest.qualities == ()
        assert guarantee_dest.caused_by.location.line == 9
        assert guarantee_dest.caused_by.location.column == 48
        assert guarantee_dest.caused_by.source_chained_name == "position<dest>"

    def test_created_particle_is_new(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == ("position<item>",)
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 30
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_origin_preserved_through_moves(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<a>.\n"
            "    define the position<b>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<a> to position<b>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 2
        assert contract.guarantees.own[0][0] == ("position<a>",)
        guarantee_a = contract.guarantees.own[0][1]
        assert isinstance(guarantee_a, action_contract.EmptyGuarantee)
        assert guarantee_a.caused_by.location.line == 8
        assert guarantee_a.caused_by.location.column == 30
        assert guarantee_a.caused_by.source_chained_name == "position<a>"
        assert contract.guarantees.own[1][0] == ("position<b>",)
        guarantee_b = contract.guarantees.own[1][1]
        assert isinstance(guarantee_b, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_b.origin_position.source_chained_name == "position<a>"
        assert guarantee_b.caused_by.location.line == 8
        assert guarantee_b.caused_by.location.column == 45
        assert guarantee_b.caused_by.source_chained_name == "position<b>"

    def test_swap_origins(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<a>.\n"
            "    define the position<b>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<temp>.\n"
            "        move the particle in position<a> to position<temp>.\n"
            "        move the particle in position<b> to position<a>.\n"
            "        move the particle in position<temp> to position<b>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 2
        assert contract.guarantees.own[0][0] == ("position<a>",)
        guarantee_a = contract.guarantees.own[0][1]
        assert isinstance(guarantee_a, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_a.origin_position.source_chained_name == "position<b>"
        assert guarantee_a.caused_by.location.line == 10
        assert guarantee_a.caused_by.location.column == 45
        assert guarantee_a.caused_by.source_chained_name == "position<a>"
        assert contract.guarantees.own[1][0] == ("position<b>",)
        guarantee_b = contract.guarantees.own[1][1]
        assert isinstance(guarantee_b, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_b.origin_position.source_chained_name == "position<a>"
        assert guarantee_b.caused_by.location.line == 11
        assert guarantee_b.caused_by.location.column == 48
        assert guarantee_b.caused_by.source_chained_name == "position<b>"

    def test_new_particle_qualities(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == ("position<item>",)
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 30


class TestChainedRequirementInference:
    def test_create_at_chain_infers_chain_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<src> to position<dest>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
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
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == chain_key
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 12
        assert guarantee.caused_by.location.column == 30
        assert guarantee.caused_by.source_chained_name == "position<item>::position</x>"

    def test_move_away_from_chain_generates_empty_guarantee(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item>::position</x> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert len(contract.guarantees.own) == 2
        assert contract.guarantees.own[0][0] == ("position<dest>",)
        guarantee_dest = contract.guarantees.own[0][1]
        assert isinstance(guarantee_dest, action_contract.OccupiedByExistingGuarantee)
        assert (
            guarantee_dest.origin_position.source_chained_name
            == "position<item>::position</x>"
        )
        assert guarantee_dest.caused_by.location.line == 13
        assert guarantee_dest.caused_by.location.column == 62
        assert guarantee_dest.caused_by.source_chained_name == "position<dest>"
        assert contract.guarantees.own[1][0] == chain_key
        guarantee = contract.guarantees.own[1][1]
        assert isinstance(guarantee, action_contract.EmptyGuarantee)
        assert guarantee.caused_by.location.line == 13
        assert guarantee.caused_by.location.column == 30
        assert guarantee.caused_by.source_chained_name == "position<item>::position</x>"

    def test_move_to_chain_generates_occupied_guarantee(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<src>.\n"
            "    define the position<dest> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<src> to position<dest>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        chain_key = ("position<dest>", "position<my.domain.com:my_lib:/x>")
        assert len(contract.guarantees.own) == 2
        assert contract.guarantees.own[0][0] == ("position<src>",)
        guarantee_src = contract.guarantees.own[0][1]
        assert isinstance(guarantee_src, action_contract.EmptyGuarantee)
        assert guarantee_src.caused_by.location.line == 13
        assert guarantee_src.caused_by.location.column == 30
        assert guarantee_src.caused_by.source_chained_name == "position<src>"
        assert contract.guarantees.own[1][0] == chain_key
        guarantee = contract.guarantees.own[1][1]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.source_chained_name == "position<src>"
        assert guarantee.caused_by.location.line == 13
        assert guarantee.caused_by.location.column == 47
        assert guarantee.caused_by.source_chained_name == "position<dest>::position</x>"

    def test_move_from_chain_away_and_back_preserves_existing_origin(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    define the position<tmp>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<item>::position</x> to position<tmp>.\n"
            "        move the particle in position<tmp> to position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert contract.guarantees.own == []

    def test_chain_guarantee_qualities(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/x>.\n"
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</x>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>::position</x>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        chain_key = ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == chain_key
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 12
        assert guarantee.caused_by.location.column == 30


class TestNoOpGuaranteeSuppression:
    def test_trigger_guarantee_suppressed_when_trigger_unchanged(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        key, guarantee = contract.guarantees.own[0]
        assert key == ("position<item>",)
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 30
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_empty_guarantee_suppressed_for_inferred_empty_position(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )
        assert contract.guarantees.own == []

    def test_empty_guarantee_emitted_for_inferred_occupied_position(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )
        assert len(contract.guarantees.own) == 1
        key, guarantee = contract.guarantees.own[0]
        assert key == ("position<item>",)
        assert isinstance(guarantee, action_contract.EmptyGuarantee)
        assert guarantee.caused_by.location.line == 7
        assert guarantee.caused_by.location.column == 33
        assert guarantee.caused_by.source_chained_name == "position<item>"

    def test_move_iface_to_local_and_back_emits_no_guarantee(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<tmp>.\n"
            "        move the particle in position<item> to position<tmp>.\n"
            "        move the particle in position<tmp> to position<item>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert (
            contract.requirements[("position<item>",)].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )
        assert contract.guarantees.own == []

    def test_trigger_guarantee_emitted_when_trigger_moves(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<dest>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        move the particle in position<run> to position<dest>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 2
        run_key, run_guarantee = contract.guarantees.own[0]
        assert run_key == ("position<run>",)
        assert isinstance(run_guarantee, action_contract.EmptyGuarantee)
        assert run_guarantee.caused_by.location.line == 7
        assert run_guarantee.caused_by.location.column == 30
        assert run_guarantee.caused_by.source_chained_name == "position<run>"
        dest_key, dest_guarantee = contract.guarantees.own[1]
        assert dest_key == ("position<dest>",)
        assert isinstance(dest_guarantee, action_contract.OccupiedByExistingGuarantee)
        assert dest_guarantee.origin_position.source_chained_name == "position<run>"
        assert dest_guarantee.caused_by.location.line == 7
        assert dest_guarantee.caused_by.location.column == 47
        assert dest_guarantee.caused_by.source_chained_name == "position<dest>"


class TestPositionInitBlockContract:
    def test_no_init_block_returns_no_contract(self):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        contracts = get_contracts(source)
        assert contracts == {}

    def test_init_block_creates_in_self(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        create a particle in position</test>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 1
        assert contract.guarantees.own[0][0] == (
            "position<my.domain.com:my_lib:/test>",
        )
        guarantee = contract.guarantees.own[0][1]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == ()
        assert guarantee.caused_by.location.line == 3
        assert guarantee.caused_by.location.column == 30

    def test_local_only_produces_empty_guarantees(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        define the position<local>.\n"
            "        create a particle in position<local>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert contract.guarantees.own == []

    def test_init_block_with_constraint_child(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</dep>.\n"
            "    }\n"
            "    after it is assigned {\n"
            "        create a particle in position</test>.\n"
            "        create a particle in position</test>::position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert len(contract.guarantees.own) == 2
        assert contract.guarantees.own[0][0] == (
            "position<my.domain.com:my_lib:/test>",
        )
        self_guarantee = contract.guarantees.own[0][1]
        assert isinstance(self_guarantee, action_contract.OccupiedByNewGuarantee)
        assert [q.full_typed_name for q in self_guarantee.qualities] == [
            "position<my.domain.com:my_lib:/dep>"
        ]
        assert self_guarantee.caused_by.location.line == 7
        assert contract.guarantees.own[1][0] == (
            "position<my.domain.com:my_lib:/test>",
            "position<my.domain.com:my_lib:/dep>",
        )
        dep_guarantee = contract.guarantees.own[1][1]
        assert isinstance(dep_guarantee, action_contract.OccupiedByNewGuarantee)
        assert dep_guarantee.qualities == ()
        assert dep_guarantee.caused_by.location.line == 8

    def test_implied_position_create_target_infers_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</dep>.\n"
            "    after it is assigned {\n"
            "        define the position<local>.\n"
            "        move the particle in position</dep> to position<local>.\n"
            "        create a particle in position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert ("position<my.domain.com:my_lib:/dep>",) in contract.requirements
        req = contract.requirements[("position<my.domain.com:my_lib:/dep>",)]
        assert req.required_state == action_contract.PositionOccupancyState.OCCUPIED
        assert req.inferred_from.location.line == 6
        assert req.inferred_from.location.column == 30
        assert req.inferred_from.location.file_path is None
        assert isinstance(req.enclosing_quality, ast.PositionDefinition)
        assert (
            req.enclosing_quality.typed_name.full_typed_name
            == "position<my.domain.com:my_lib:/test>"
        )
        assert req.propagated_from is None

    def test_implied_position_destroy_target_infers_occupied(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</dep>.\n"
            "    after it is assigned {\n"
            "        destroy the particle in position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert ("position<my.domain.com:my_lib:/dep>",) in contract.requirements
        req = contract.requirements[("position<my.domain.com:my_lib:/dep>",)]
        assert req.required_state == action_contract.PositionOccupancyState.OCCUPIED
        assert req.inferred_from.location.line == 5
        assert req.inferred_from.location.column == 33
        assert req.inferred_from.location.file_path is None
        assert isinstance(req.enclosing_quality, ast.PositionDefinition)
        assert (
            req.enclosing_quality.typed_name.full_typed_name
            == "position<my.domain.com:my_lib:/test>"
        )
        assert req.propagated_from is None

    def test_implied_position_move_destination_infers_empty(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</dep>.\n"
            "    after it is assigned {\n"
            "        define the position<local>.\n"
            "        create a particle in position<local>.\n"
            "        move the particle in position<local> to position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert ("position<my.domain.com:my_lib:/dep>",) in contract.requirements
        req = contract.requirements[("position<my.domain.com:my_lib:/dep>",)]
        assert req.required_state == action_contract.PositionOccupancyState.EMPTY
        assert req.inferred_from.location.line == 7
        assert req.inferred_from.location.column == 49
        assert req.inferred_from.location.file_path is None
        assert isinstance(req.enclosing_quality, ast.PositionDefinition)
        assert (
            req.enclosing_quality.typed_name.full_typed_name
            == "position<my.domain.com:my_lib:/test>"
        )
        assert req.propagated_from is None

    def test_chained_name_intermediate_implied_parent_infers_occupied(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/grand_child>.\n"
            "define the potential position<my.domain.com:my_lib:/dep> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</grand_child>.\n"
            "    }\n"
            "}\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</dep>.\n"
            "    after it is assigned {\n"
            "        destroy the particle in position</dep>::position</grand_child>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert ("position<my.domain.com:my_lib:/dep>",) in contract.requirements
        parent_req = contract.requirements[("position<my.domain.com:my_lib:/dep>",)]
        assert (
            parent_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
        )
        assert parent_req.inferred_from.location.line == 10
        assert parent_req.inferred_from.location.column == 33
        assert parent_req.inferred_from.location.file_path is None
        assert isinstance(parent_req.enclosing_quality, ast.PositionDefinition)
        assert (
            parent_req.enclosing_quality.typed_name.full_typed_name
            == "position<my.domain.com:my_lib:/test>"
        )
        assert parent_req.propagated_from is None
        leaf_key = (
            "position<my.domain.com:my_lib:/dep>",
            "position<my.domain.com:my_lib:/grand_child>",
        )
        assert leaf_key in contract.requirements
        leaf_req = contract.requirements[leaf_key]
        assert (
            leaf_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
        )
        assert leaf_req.inferred_from.location.line == 10
        assert leaf_req.inferred_from.location.column == 33
        assert leaf_req.inferred_from.location.file_path is None
        assert isinstance(leaf_req.enclosing_quality, ast.PositionDefinition)
        assert (
            leaf_req.enclosing_quality.typed_name.full_typed_name
            == "position<my.domain.com:my_lib:/test>"
        )
        assert leaf_req.propagated_from is None

    def test_self_reference_does_not_publish_requirement(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/dep>.\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</dep>.\n"
            "    }\n"
            "    after it is assigned {\n"
            "        destroy the particle in position</test>::position</dep>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert contract.requirements == {}

    def test_direct_operation_on_self_does_not_publish_requirement(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        create a particle in position</test>.\n"
            "        destroy the particle in position</test>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"position<my.domain.com:my_lib:/test>"}
        contract = contracts["position<my.domain.com:my_lib:/test>"]
        assert contract.requirements == {}


def test_interface_position_requirement_integration():
    source = (
        "define the potential action<my.domain.com:my_lib:/inner> {\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<item>.\n"
        "    define the position<dest>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<item> to position<dest>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/middle> {\n"
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
        "define the potential action<my.domain.com:my_lib:/outer> {\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<out_iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</middle>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<out_iface>::action</middle>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    )
    contracts = get_contracts(source)
    assert contracts.keys() == {
        "action<my.domain.com:my_lib:/inner>",
        "action<my.domain.com:my_lib:/middle>",
        "action<my.domain.com:my_lib:/outer>",
    }
    outer_contract = contracts["action<my.domain.com:my_lib:/outer>"]
    req_key = (
        "position<out_iface>",
        "action<my.domain.com:my_lib:/middle>",
        "position<mid_iface>",
        "action<my.domain.com:my_lib:/inner>",
        "position<item>",
    )
    req = outer_contract.requirements[req_key]

    assert req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert (
        req.enclosing_quality.typed_name.full_typed_name
        == "action<my.domain.com:my_lib:/outer>"
    )
    assert (
        req.inferred_from.source_chained_name == "position<out_iface>::action</middle>"
    )
    assert req.inferred_from.location.line == 34
    assert req.inferred_from.location.file_path is None

    assert req.propagated_from is not None
    mid_req = req.propagated_from
    assert mid_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert (
        mid_req.enclosing_quality.typed_name.full_typed_name
        == "action<my.domain.com:my_lib:/middle>"
    )
    assert (
        mid_req.inferred_from.source_chained_name
        == "position<mid_iface>::action</inner>"
    )
    assert mid_req.inferred_from.location.line == 21
    assert mid_req.inferred_from.location.file_path is None

    assert mid_req.propagated_from is not None
    inner_req = mid_req.propagated_from
    assert inner_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert (
        inner_req.enclosing_quality.typed_name.full_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )
    assert inner_req.inferred_from.source_chained_name == "position<item>"
    assert inner_req.inferred_from.location.line == 8
    assert inner_req.inferred_from.location.file_path is None
    assert inner_req.propagated_from is None

    assert req.root_cause_quality_name() == "action<my.domain.com:my_lib:/inner>"
    outer_fqun = req.enclosing_quality.typed_name.name_content.fqun
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
    assert outer_locs[0].line == 21
    assert outer_locs[0].file_path is None
    assert outer_locs[1].line == 8
    assert outer_locs[1].file_path is None

    assert mid_req.root_cause_quality_name() == "action<my.domain.com:my_lib:/inner>"
    middle_fqun = mid_req.enclosing_quality.typed_name.name_content.fqun
    assert _resolved(mid_req, middle_fqun) == (
        "position<mid_iface>::action</inner>::position<item>"
    )
    assert mid_req.full_propagation_position_chain().source_chained_name == (
        "position<mid_iface>::action</inner>::position<item>"
    )
    mid_locs = mid_req.propagated_from_locations()
    assert len(mid_locs) == 1
    assert mid_locs[0].line == 8
    assert mid_locs[0].file_path is None

    assert inner_req.root_cause_quality_name() == "action<my.domain.com:my_lib:/inner>"
    inner_fqun = inner_req.enclosing_quality.typed_name.name_content.fqun
    assert _resolved(inner_req, inner_fqun) == "position<item>"
    assert (
        inner_req.full_propagation_position_chain().source_chained_name
        == "position<item>"
    )
    assert inner_req.propagated_from_locations() == []


def test_init_block_propagation_records_occupied_on_inner_contract():
    source = (
        "define the potential position<my.domain.com:my_lib:/q>.\n"
        "define the potential position<my.domain.com:my_lib:/p> {\n"
        "    it also assigns the position</q>.\n"
        "    after it is assigned {\n"
        "        destroy the particle in position</q>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/inner> {\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</p>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<iface>.\n"
        "    }\n"
        "}\n"
    )
    contracts = get_contracts(source)
    assert contracts.keys() == {
        "position<my.domain.com:my_lib:/p>",
        "action<my.domain.com:my_lib:/inner>",
    }
    inner_contract = contracts["action<my.domain.com:my_lib:/inner>"]

    assert inner_contract.requirements.keys() == {
        ("position<iface>",),
        ("position<iface>", "position<my.domain.com:my_lib:/q>"),
    }

    direct_req = inner_contract.requirements[("position<iface>",)]
    assert direct_req.required_state == action_contract.PositionOccupancyState.EMPTY
    assert direct_req.inferred_from.source_chained_name == "position<iface>"
    assert direct_req.inferred_from.location.line == 18
    assert direct_req.inferred_from.location.column == 30
    assert direct_req.inferred_from.location.end_line == 18
    assert direct_req.inferred_from.location.end_column == 45
    assert direct_req.inferred_from.location.file_path is None
    assert (
        direct_req.enclosing_quality.typed_name.source_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )
    assert direct_req.propagated_from is None

    propagated_req = inner_contract.requirements[
        ("position<iface>", "position<my.domain.com:my_lib:/q>")
    ]
    assert (
        propagated_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    )
    assert propagated_req.inferred_from.source_chained_name == "position<iface>"
    assert propagated_req.inferred_from.location.line == 18
    assert propagated_req.inferred_from.location.column == 30
    assert propagated_req.inferred_from.location.end_line == 18
    assert propagated_req.inferred_from.location.end_column == 45
    assert propagated_req.inferred_from.location.file_path is None
    assert (
        propagated_req.enclosing_quality.typed_name.source_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )

    p_req = propagated_req.propagated_from
    assert p_req is not None
    assert p_req.required_state == action_contract.PositionOccupancyState.OCCUPIED
    assert p_req.inferred_from.source_chained_name == "position</q>"
    assert p_req.inferred_from.location.line == 5
    assert p_req.inferred_from.location.column == 33
    assert p_req.inferred_from.location.end_line == 5
    assert p_req.inferred_from.location.end_column == 45
    assert p_req.inferred_from.location.file_path is None
    assert (
        p_req.enclosing_quality.typed_name.source_typed_name
        == "position<my.domain.com:my_lib:/p>"
    )
    assert p_req.propagated_from is None

    assert propagated_req.full_propagation_position_chain().source_chained_name == (
        "position<iface>::position</q>"
    )
    assert (
        propagated_req.root_cause_quality_name() == "position<my.domain.com:my_lib:/p>"
    )
    propagated_locations = propagated_req.propagated_from_locations()
    assert len(propagated_locations) == 1
    assert propagated_locations[0].line == 5
    assert propagated_locations[0].column == 33
    assert propagated_locations[0].end_line == 5
    assert propagated_locations[0].end_column == 45
    assert propagated_locations[0].file_path is None


def test_init_block_propagation_records_empty_on_inner_contract():
    source = (
        "define the potential position<my.domain.com:my_lib:/q>.\n"
        "define the potential position<my.domain.com:my_lib:/p> {\n"
        "    it also assigns the position</q>.\n"
        "    after it is assigned {\n"
        "        create a particle in position</q>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/inner> {\n"
        "    define the position<trigger_pos>.\n"
        "    define the position<iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</p>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<iface>.\n"
        "    }\n"
        "}\n"
    )
    contracts = get_contracts(source)
    assert contracts.keys() == {
        "position<my.domain.com:my_lib:/p>",
        "action<my.domain.com:my_lib:/inner>",
    }
    inner_contract = contracts["action<my.domain.com:my_lib:/inner>"]

    assert inner_contract.requirements.keys() == {
        ("position<iface>",),
        ("position<iface>", "position<my.domain.com:my_lib:/q>"),
    }

    direct_req = inner_contract.requirements[("position<iface>",)]
    assert direct_req.required_state == action_contract.PositionOccupancyState.EMPTY
    assert direct_req.inferred_from.source_chained_name == "position<iface>"
    assert direct_req.inferred_from.location.line == 18
    assert direct_req.inferred_from.location.column == 30
    assert direct_req.inferred_from.location.end_line == 18
    assert direct_req.inferred_from.location.end_column == 45
    assert direct_req.inferred_from.location.file_path is None
    assert (
        direct_req.enclosing_quality.typed_name.source_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )
    assert direct_req.propagated_from is None

    propagated_req = inner_contract.requirements[
        ("position<iface>", "position<my.domain.com:my_lib:/q>")
    ]
    assert propagated_req.required_state == action_contract.PositionOccupancyState.EMPTY
    assert propagated_req.inferred_from.source_chained_name == "position<iface>"
    assert propagated_req.inferred_from.location.line == 18
    assert propagated_req.inferred_from.location.column == 30
    assert propagated_req.inferred_from.location.end_line == 18
    assert propagated_req.inferred_from.location.end_column == 45
    assert propagated_req.inferred_from.location.file_path is None
    assert (
        propagated_req.enclosing_quality.typed_name.source_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )

    p_req = propagated_req.propagated_from
    assert p_req is not None
    assert p_req.required_state == action_contract.PositionOccupancyState.EMPTY
    assert p_req.inferred_from.source_chained_name == "position</q>"
    assert p_req.inferred_from.location.line == 5
    assert p_req.inferred_from.location.column == 30
    assert p_req.inferred_from.location.end_line == 5
    assert p_req.inferred_from.location.end_column == 42
    assert p_req.inferred_from.location.file_path is None
    assert (
        p_req.enclosing_quality.typed_name.source_typed_name
        == "position<my.domain.com:my_lib:/p>"
    )
    assert p_req.propagated_from is None

    assert propagated_req.full_propagation_position_chain().source_chained_name == (
        "position<iface>::position</q>"
    )
    assert (
        propagated_req.root_cause_quality_name() == "position<my.domain.com:my_lib:/p>"
    )
    propagated_locations = propagated_req.propagated_from_locations()
    assert len(propagated_locations) == 1
    assert propagated_locations[0].line == 5
    assert propagated_locations[0].column == 30
    assert propagated_locations[0].end_line == 5
    assert propagated_locations[0].end_column == 42
    assert propagated_locations[0].file_path is None


class TestDestructorContract:
    def test_destructor_contract_has_empty_trigger_position_name(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert isinstance(contract, action_contract.ActionContract)
        assert contract.trigger_position_name == ""

    def test_destructor_body_infers_requirements_normally(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<victim>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        destroy the particle in position<victim>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert contract.requirements.keys() == {("position<victim>",)}
        assert (
            contract.requirements[("position<victim>",)].required_state
            == action_contract.PositionOccupancyState.OCCUPIED
        )

    def test_destructor_interface_position_create_infers_empty(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<slot>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<slot>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert contract.requirements.keys() == {("position<slot>",)}
        assert (
            contract.requirements[("position<slot>",)].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )

    def test_destructor_guarantee_is_replaced_with_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<slot>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<slot>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert [type(guarantee) for _key, guarantee in contract.guarantees.own] == [
            action_contract.ErrorGuarantee
        ]

    def test_destructor_preexisting_error_guarantee_passes_through(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<sink>.\n"
            "        define the position<sink2>.\n"
            "        move the particle in position<item> to position<sink>.\n"
            "        move the particle in position<item> to position<sink2>.\n"
            "    }\n"
            "}\n"
        )
        contracts = get_contracts(source)
        assert contracts.keys() == {"action<my.domain.com:my_lib:/test>"}
        contract = contracts["action<my.domain.com:my_lib:/test>"]
        assert [type(guarantee) for _key, guarantee in contract.guarantees.own] == [
            action_contract.ErrorGuarantee
        ]


def test_destructors_fire_in_reverse_assignment_order():
    source = (
        "define the potential action<my.domain.com:my_lib:/destructor_first> {\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/destructor_second> {\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the action</destructor_first>.\n"
        "                it has the action</destructor_second>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "        destroy the particle in position<box>.\n"
        "    }\n"
        "}\n"
    )
    results = get_results(source)
    test_result = results["action<my.domain.com:my_lib:/test>"]
    assert [edge.target for edge in test_result.edges] == [
        "action<my.domain.com:my_lib:/destructor_second>",
        "action<my.domain.com:my_lib:/destructor_first>",
    ]
