# pyright: reportUnusedCallResult=false

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

# --- Dead Child Positions ---


def test_unreferenced_child_position_on_local_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_unreferenced_child_position_on_interface_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24


def test_child_position_referenced_by_create_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</thing>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_child_position_referenced_as_move_source_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</thing>.\n"
                "        move the particle in position<box>::position</thing> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_child_position_required_by_move_destination_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<box> to position<dest>.\n"
                "        create a particle in position<dest>::position</thing>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_child_position_required_by_move_destination_through_multiple_hops_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        define the position<mid>.\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<box> to position<mid>.\n"
                "        move the particle in position<mid> to position<dest>.\n"
                "        create a particle in position<dest>::position</thing>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_redundant_destination_constraint_on_move_filled_position_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</thing>.\n"
                "        move the particle in position<box> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 28


def test_constraint_on_interface_position_filled_by_create_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_constraint_on_interface_position_filled_then_destroyed_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "        destroy the particle in position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 24


def test_constraint_on_interface_position_filled_by_moving_new_particle_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_constraint_on_interface_position_filled_by_moving_caller_particle_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<in_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    define the position<out_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in_iface> to position<out_iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_unused_constraint_on_inferred_occupied_input_interface_is_dead_via_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "            it has the position</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 24


def test_unused_constraint_on_inferred_occupied_input_interface_is_dead_via_move_from_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "            it has the position</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src>.\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<iface>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 24


def test_unused_constraint_on_inferred_occupied_input_interface_is_dead_via_move_from_interface(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "c.dfn": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<in_iface>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "            it has the position</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in_iface> to position<iface>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</c>"
    assert all_diags[0].position_name == "position<iface>"
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 24


def test_dead_child_position_inside_constructor(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 28


def test_one_child_position_dead_while_a_sibling_is_referenced(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</b>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 28


def test_constraint_that_only_provides_a_moved_quality_by_implication_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the position</child>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box1> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box2> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box1>.\n"
                "        move the particle in position<box1> to position<box2>.\n"
                "        move the particle in position<box2> to position<dest>.\n"
                "        destroy the particle in position<dest>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<box2>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 28


def test_implied_child_position_of_constructor_is_not_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the position</child>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


# --- Untriggered Actions ---


def test_untriggered_action_on_local_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</coin>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_untriggered_action_on_interface_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</coin>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</coin>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24


def test_triggered_action_via_create_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</coin>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_triggered_action_via_move_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        define the position<feeder>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<feeder>.\n"
                "        move the particle in position<feeder> to position<box>::action</coin>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_action_interface_filled_but_never_triggered_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "twoport.dfn": (
                "define the potential action<my.domain.com:my_lib:/twoport> {\n"
                "    define the position<go>.\n"
                "    define the position<slot>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<slot>.\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</twoport>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</twoport>::position<slot>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</twoport>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28


def test_action_required_by_move_destination_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<box> to position<dest>.\n"
                "        create a particle in position<dest>::action</coin>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_constraint_that_only_provides_a_triggered_action_by_implication_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the action</child>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in action</child>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box1> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box2> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box1>.\n"
                "        move the particle in position<box1> to position<box2>.\n"
                "        create a particle in position<box2>::action</child>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<box2>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 28


def test_implied_action_of_constructor_is_not_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the action</child>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in action</child>::position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_destructor_constraint_is_never_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "cleanup.dfn": (
                "define the potential action<my.domain.com:my_lib:/cleanup> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "                it has the action</cleanup>.\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[1].constraint_name == "action</coin>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 10
    assert all_diags[1].location.column == 28


def test_constructor_constraint_reached_only_by_move_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "cleanup.dfn": (
                "define the potential action<my.domain.com:my_lib:/cleanup> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box1> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "                it has the action</cleanup>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box2> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "                it has the action</cleanup>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box1>.\n"
                "        move the particle in position<box1> to position<box2>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # Unlike a destructor, a constructor is only alive when triggered. Moving a
    # particle into box2 does not trigger box2's constructor, so its constraint
    # is dead, while box2's destructor constraint stays exempt.
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<box2>"
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 28


def test_constructor_on_local_position_alive_via_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # Creating a particle in box triggers its constructor, keeping the
    # constraint alive.
    assert_no_errors(result.program_result)


def test_constructor_on_interface_position_alive_via_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<slot> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<slot>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # Creating a particle in the interface position triggers its constructor.
    assert_no_errors(result.program_result)


def test_constructor_on_interface_position_dead_when_never_created(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # The trigger particle is supplied by the caller, not created here, so its
    # constructor never runs in /test, leaving the constraint dead.
    #
    # TODO: However, this means that actions can never demand a constructor
    # on their interface positions, so maybe we should rethink this.
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24


# --- Combined and cross-definition cases ---


def test_dead_child_position_and_untriggered_action_on_same_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "coin.dfn": (
                "define the potential action<my.domain.com:my_lib:/coin> {\n"
                "    define the position<go>.\n"
                "    it happens when {\n"
                "        the position<go> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<go>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "                it has the action</coin>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[1].constraint_name == "action</coin>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 9
    assert all_diags[1].location.column == 28


def test_interface_constraint_referenced_only_in_another_definition_is_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "consumer.dfn": (
                "define the potential action<my.domain.com:my_lib:/consumer> {\n"
                "    define the position<run> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</thing>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<start>.\n"
                "    it happens when {\n"
                "        the position<start> has a particle.\n"
                "    } and it does {\n"
                "        define the position<holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</consumer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<holder>.\n"
                "        create a particle in position<holder>::action</consumer>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</thing>"
    assert all_diags[0].position_name == "position<run>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path is not None
    assert all_diags[0].location.file_path.name == "consumer.dfn"


def test_child_position_referenced_as_move_target_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</thing>.\n"
                "            }\n"
                "        }\n"
                "        define the position<src>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<box>::position</thing>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_child_position_referenced_only_as_inferred_requirement_intermediate_is_alive(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::position</a>::position</b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_two_child_positions_on_one_position_are_both_dead(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[0].constraint_name == "position</a>"
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 28
    assert isinstance(all_diags[1], diagnostics.DeadChildPositionDiagnostic)
    assert all_diags[1].constraint_name == "position</b>"
    assert all_diags[1].position_name == "position<box>"
    assert all_diags[1].location.line == 9
    assert all_diags[1].location.column == 28


def test_unreferenced_constraint_on_global_position_is_not_checked(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "thing.dfn": "define the potential position<my.domain.com:my_lib:/thing>.\n",
            "container.dfn": (
                "define the potential position<my.domain.com:my_lib:/container> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</thing>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</container>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</container>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
