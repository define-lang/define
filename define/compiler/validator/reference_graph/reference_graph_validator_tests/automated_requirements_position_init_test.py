# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_init_block_occupied_violation_via_destroy_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_occupied_violation_via_move_source_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position</q> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 5
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_empty_violation_via_create_in_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.filled_at.line == 3
    assert diag.filled_at.column == 37
    assert diag.filled_at.file_path == PurePosixPath("q.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_satisfied_requirement_emits_no_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_multiple_implied_positions_each_check_runs(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "r.dfn": "define the potential position<my.domain.com:my_lib:/r>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    it also assigns the position</r>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>.\n"
                "        destroy the dimension point in position</r>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    diag_q = all_diags[0]
    diag_r = all_diags[1]
    assert isinstance(
        diag_q, diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert diag_q.create_target_name == "position<box>"
    assert diag_q.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag_q.position_name == "position<box>::position</q>"
    assert diag_q.location.line == 11
    assert diag_q.location.column == 37
    assert diag_q.location.file_path == PurePosixPath("test.dfn")
    assert diag_q.inferred_at.line == 5
    assert diag_q.inferred_at.column == 40
    assert diag_q.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag_q.propagated_from_locations == []
    assert isinstance(
        diag_r, diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert diag_r.create_target_name == "position<box>"
    assert diag_r.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag_r.position_name == "position<box>::position</r>"
    assert diag_r.location.line == 11
    assert diag_r.location.column == 37
    assert diag_r.location.file_path == PurePosixPath("test.dfn")
    assert diag_r.inferred_at.line == 6
    assert diag_r.inferred_at.column == 40
    assert diag_r.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag_r.propagated_from_locations == []


def test_self_reference_in_init_block_publishes_no_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</p>.\n"
                "        create a dimension point in position</p>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_occupied_violation_via_destroy_of_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_occupied_violation_via_move_source_of_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position</q>::position</child> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 5
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_empty_violation_via_create_in_child_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>::position</child>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.filled_at.line == 7
    assert diag.filled_at.column == 37
    assert diag.filled_at.file_path == PurePosixPath("q.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_satisfied_requirement_for_child_of_implied_emits_no_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_init_block_occupied_violation_via_destroy_of_grandchild_of_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "grandchild.dfn": "define the potential position<my.domain.com:my_lib:/grandchild>.\n",
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>::position</child>::position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        diag.position_name
        == "position<box>::position</q>::position</child>::position</grandchild>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_occupied_violation_via_destroy_of_iface_of_action_in_implied_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<iface>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</a>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</outer>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</outer>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>::position</outer>::action</a>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []


def test_init_block_occupied_violation_via_destroy_of_child_of_iface_of_action_in_implied_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</a>.\n"
                "    }\n"
                "}\n"
            ),
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</outer>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</outer>.\n"
                "        create a dimension point in position</q>::position</outer>::action</a>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</q>::position</outer>::action</a>::position<iface>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        diag.position_name
        == "position<box>::position</q>::position</outer>::action</a>::position<iface>::position</child>"
    )
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []
