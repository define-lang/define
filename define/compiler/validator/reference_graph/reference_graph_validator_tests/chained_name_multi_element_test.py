# pyright: reportUnusedCallResult=false
"""Multi-element chain tests, including chains that pass through actions."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestCreateParticle:
    def test_chain_third_element_in_position_constraints(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_chain_third_element_not_in_position_constraints(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
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
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
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
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_chain_after_action_with_local_not_in_action_stops_walking(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInterfacePositionDiagnostic
        )
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 16
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.end_line == 16
        assert all_diags[0].location.end_column == 80
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_element_inside_action_not_found(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInterfacePositionDiagnostic
        )
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_element_inside_action_no_block(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInterfacePositionDiagnostic
        )
        assert all_diags[0].element_name == "position<pos_c>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 63
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_five_element_alternating_chain(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_four_element_chain_through_positions(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_chain_action_cannot_contain_action(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainGlobalNameAfterActionDiagnostic
        )
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/bar>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/foo>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 57
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_action_cannot_contain_action_stops_at_first_failure(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainGlobalNameAfterActionDiagnostic
        )
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/b>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/a>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_action_then_action_short(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


class TestChainActionValidation:
    def test_local_action_name_after_action_rejected(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph(max_workers=1)
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.LocalActionNameDiagnostic)
        assert all_diags[0].local_name == "bad"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 55
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(all_diags[1], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[1].location.line == 10
        assert all_diags[1].location.column == 55
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")

    def test_chain_through_action_with_constrained_local_position(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph(max_workers=1)
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
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph(max_workers=1)
        assert_no_errors(result.program_result)

    def test_deferred_chain_continuation_through_action_produces_error(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph(max_workers=1)
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
