# pyright: reportUnusedCallResult=false

from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
)
from define.compiler.validator.structural import program_validator


def _get_contract(
    source: str,
    action_name: str = "action<my.domain.com:my_lib:/test>",
) -> action_contract.ActionContract:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.has_errors(), result.all_diagnostics
    definition_result = result.definition_results[action_name]
    validator = definition_postorder_validator.create_postorder_validator(
        definition_result, result.definition_results, {}
    )
    _, _, contract = validator.analyze()
    if contract is None:
        raise ValueError(f"No contract for {action_name}")
    return contract


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
        assert "item" in contract.requirements
        assert (
            contract.requirements["item"].required_state
            == action_contract.PositionOccupancyState.EMPTY
        )
        assert contract.requirements["item"].inferred_from.line == 7

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
            contract.requirements["item"].required_state
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
            contract.requirements["dest"].required_state
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
        assert "run" not in contract.requirements
        assert contract.trigger_position_name == "run"

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
            contract.requirements["item"].required_state
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
        assert "local_only" not in contract.requirements

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
        guarantee = contract.guarantees["item"]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.caused_by.line == 7

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
        assert isinstance(contract.guarantees["item"], action_contract.EmptyGuarantee)

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
        guarantee = contract.guarantees["run"]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.typed_name.name_content.name == "run"

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
        assert isinstance(
            contract.guarantees["item"], action_contract.OccupiedByNewGuarantee
        )

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
        guarantee = contract.guarantees["b"]
        assert isinstance(guarantee, action_contract.OccupiedByExistingGuarantee)
        assert guarantee.origin_position.typed_name.name_content.name == "a"

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
        guarantee_a = contract.guarantees["a"]
        assert isinstance(guarantee_a, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_a.origin_position.typed_name.name_content.name == "b"
        guarantee_b = contract.guarantees["b"]
        assert isinstance(guarantee_b, action_contract.OccupiedByExistingGuarantee)
        assert guarantee_b.origin_position.typed_name.name_content.name == "a"

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
        guarantee = contract.guarantees["item"]
        assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)
        assert guarantee.qualities == frozenset()
