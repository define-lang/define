# pyright: reportUnusedCallResult=false
"""Multi-element chain tests, including chains that pass through actions."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


class TestCreateParticle:
    def test_chain_third_element_in_position_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::position</pos_b>.\n"
                    "        create a particle in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.dfn": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            }
        )
        assert_no_errors(result.program_result)

    def test_chain_third_element_not_in_position_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::position</pos_b>::position</wrong>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.dfn": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
                "wrong.dfn": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 65
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_third_element_position_no_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.dfn": "define the potential position<my.domain.com:my_lib:/pos_b>.\n",
                "pos_c.dfn": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/pos_c>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 65
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_element_inside_action_valid(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pos_c>.\n"
                    "    it happens when {\n"
                    "        the position<pos_c> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert_no_errors(result.program_result)

    def test_chain_after_action_with_local_not_in_action_stops_walking(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        """Chain walking stops when a local element after an action isn't in the action's interfaces.

        Even when the chain continues beyond that element, only one diagnostic
        is emitted and walking stops — it does not advance as if one element
        were consumed (which would treat a local element as a global parent
        and crash).
        """
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<no_such>::position</later>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "later.dfn": (
                    "define the potential position<my.domain.com:my_lib:/later>.\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.end_line == 10
        assert all_diags[0].location.end_column == 80
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_element_inside_action_not_found(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<no_such>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pos_c>.\n"
                    "    it happens when {\n"
                    "        the position<pos_c> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_element_inside_action_no_block(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<_noop>.\n"
                    "    it happens when {\n"
                    "        the position<_noop> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<__noop>.\n"
                    "        create a particle in position<__noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<pos_c>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_five_element_alternating_chain(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<pos_c>.\n"
                    "        create a particle in position<pos_a>::action</act_b>::position<pos_c>::action</act_d>::position<pos_e>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pos_c> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_d>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_c> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_d.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_d> {\n"
                    "    define the position<pos_e>.\n"
                    "    it happens when {\n"
                    "        the position<pos_e> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert_no_errors(result.program_result)

    def test_four_element_chain_through_positions(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<pos_a>::position</pos_b>.\n"
                    "        create a particle in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                    "        create a particle in position<pos_a>::position</pos_b>::position</pos_c>::position</pos_d>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos_c> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</pos_d>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_d.dfn": "define the potential position<my.domain.com:my_lib:/pos_d>.\n",
            }
        )
        assert_no_errors(result.program_result)

    def test_chain_action_cannot_contain_action(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</foo>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</foo>::action</bar>::position<y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "foo.dfn": (
                    "define the potential action<my.domain.com:my_lib:/foo> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "bar.dfn": (
                    "define the potential action<my.domain.com:my_lib:/bar> {\n"
                    "    define the position<y>.\n"
                    "    it happens when {\n"
                    "        the position<y> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/bar>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/foo>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 57
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_action_cannot_contain_action_stops_at_first_failure(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</a>::action</b>::position<bogus>.\n"
                    "    }\n"
                    "}\n"
                ),
                "a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/a> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/b> {\n"
                    "    define the position<other>.\n"
                    "    it happens when {\n"
                    "        the position<other> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/b>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/a>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_action_then_action_short(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</a>::action</b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/a> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/b> {\n"
                    "    define the position<_noop>.\n"
                    "    it happens when {\n"
                    "        the position<_noop> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<__noop>.\n"
                    "        create a particle in position<__noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


class TestChainActionValidation:
    def test_local_action_name_after_action_rejected(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</a>::action<bad>.\n"
                    "    }\n"
                    "}\n"
                ),
                "a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/a> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
            max_workers=1,
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(all_diags[1], diagnostics.LocalActionNameDiagnostic)
        assert all_diags[1].local_name == "bad"
        assert all_diags[1].location.line == 10
        assert all_diags[1].location.column == 62
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")

    def test_chain_through_action_with_constrained_local_position(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</act>::position<inner>::position</wrong>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</allowed>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "allowed.dfn": "define the potential position<my.domain.com:my_lib:/allowed>.\n",
                "wrong.dfn": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            },
            max_workers=1,
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<inner>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 74
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_through_action_valid_continuation(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</act>::position<inner>.\n"
                    "        create a particle in position<x>::action</act>::position<inner>::position</deeper>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</deeper>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "deeper.dfn": "define the potential position<my.domain.com:my_lib:/deeper>.\n",
            },
            max_workers=1,
        )
        assert_no_errors(result.program_result)

    def test_deferred_chain_continuation_through_action_produces_error(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>::action</act>::position<inner>::position</target>::position</leaf>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</target>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "target.dfn": (
                    "define the potential position<my.domain.com:my_lib:/target> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the position</allowed_leaf>.\n"
                    "    }\n"
                    "}\n"
                ),
                "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
                "allowed_leaf.dfn": "define the potential position<my.domain.com:my_lib:/allowed_leaf>.\n",
            },
            max_workers=1,
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/leaf>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/target>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 93
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
