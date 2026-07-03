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
        assert len(contract.guarantees.own) == 2
        # position<item> was created and moved away: it ends empty, as required,
        # but the body touched it, so it is guaranteed unchanged.
        item_key, item_guarantee = contract.guarantees.own[0]
        assert item_key == ("position<item>",)
        assert isinstance(item_guarantee, action_contract.UnchangedGuarantee)
        assert item_guarantee.caused_by.location.line == 9
        assert item_guarantee.caused_by.location.column == 30
        assert item_guarantee.caused_by.source_chained_name == "position<item>"
        dest_key, dest_guarantee = contract.guarantees.own[1]
        assert dest_key == ("position<dest>",)
        assert isinstance(dest_guarantee, action_contract.OccupiedByNewGuarantee)
        assert dest_guarantee.qualities == ()
        assert dest_guarantee.caused_by.location.line == 9
        assert dest_guarantee.caused_by.location.column == 48
        assert dest_guarantee.caused_by.source_chained_name == "position<dest>"

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

    def test_move_from_chain_away_and_back_emits_unchanged(self):
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
        assert len(contract.guarantees.own) == 2
        # position<tmp> is an interface scratch position moved through and left
        # empty: touched but unchanged. It sorts first (shorter key).
        tmp_key, tmp_guarantee = contract.guarantees.own[0]
        assert tmp_key == ("position<tmp>",)
        assert isinstance(tmp_guarantee, action_contract.UnchangedGuarantee)
        chain_key, chain_guarantee = contract.guarantees.own[1]
        assert chain_key == ("position<item>", "position<my.domain.com:my_lib:/x>")
        assert isinstance(chain_guarantee, action_contract.UnchangedGuarantee)

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

    def test_unchanged_guarantee_for_touched_inferred_empty_position(self):
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
        assert len(contract.guarantees.own) == 1
        key, guarantee = contract.guarantees.own[0]
        assert key == ("position<item>",)
        assert isinstance(guarantee, action_contract.UnchangedGuarantee)

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

    def test_move_iface_to_local_and_back_emits_unchanged(self):
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
        assert len(contract.guarantees.own) == 1
        key, guarantee = contract.guarantees.own[0]
        assert key == ("position<item>",)
        assert isinstance(guarantee, action_contract.UnchangedGuarantee)

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
        req.enclosing_action.typed_name.full_typed_name
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
        mid_req.enclosing_action.typed_name.full_typed_name
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
        inner_req.enclosing_action.typed_name.full_typed_name
        == "action<my.domain.com:my_lib:/inner>"
    )
    assert inner_req.inferred_from.source_chained_name == "position<item>"
    assert inner_req.inferred_from.location.line == 8
    assert inner_req.inferred_from.location.file_path is None
    assert inner_req.propagated_from is None

    assert req.root_cause_action_name() == "action<my.domain.com:my_lib:/inner>"
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
    assert outer_locs[0].line == 21
    assert outer_locs[0].file_path is None
    assert outer_locs[1].line == 8
    assert outer_locs[1].file_path is None

    assert mid_req.root_cause_action_name() == "action<my.domain.com:my_lib:/inner>"
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
    assert mid_locs[0].file_path is None

    assert inner_req.root_cause_action_name() == "action<my.domain.com:my_lib:/inner>"
    inner_fqun = inner_req.enclosing_action.typed_name.name_content.fqun
    assert _resolved(inner_req, inner_fqun) == "position<item>"
    assert (
        inner_req.full_propagation_position_chain().source_chained_name
        == "position<item>"
    )
    assert inner_req.propagated_from_locations() == []


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
