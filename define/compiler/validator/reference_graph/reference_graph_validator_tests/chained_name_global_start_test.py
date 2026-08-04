# pyright: reportUnusedCallResult=false
"""Chained reference tests for self-references and atypical chain starts."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataNonFilesystemWithReferenceGraph,
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestUnnecessarySelfReference:
    def test_destroy_self_reference_in_chain(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == (
            "action<mv:define-lang.org:test_files:/invalid/references/unnecessary_self_reference>"
        )
        assert diags[0].location.line == 8
        assert diags[0].location.column == 33
        assert diags[0].location.end_line == 8
        assert diags[0].location.end_column == 87
        assert diags[0].location.file_path is None

    def test_self_reference_in_chain(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 7
        assert diags[0].location.column == 30
        assert diags[0].message == (
            "the reference to 'action<my.domain.com:my_lib:/test>' is not necessary"
            " because the code is already inside that definition"
        )

    def test_self_reference_stops_further_chain_validation(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 30

    def test_self_reference_suppresses_downstream_diagnostics(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 7
        assert diags[0].location.column == 30

    def test_single_element_self_reference_not_stripped(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[0].location.line == 6
        assert diags[0].location.column == 30
        assert isinstance(diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
        assert diags[1].location.line == 6
        assert diags[1].location.column == 30
        assert diags[1].cycle == [
            "action<my.domain.com:my_lib:/test>",
            "action<my.domain.com:my_lib:/test>",
        ]


class TestUnknownGlobalChainStart:
    def test_no_constraint_check_on_unknown_global(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "action</other>"
        assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
        assert all_diags[0].location.line == 6
        assert all_diags[0].location.column == 30
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


class TestImpliedQualityChainStart:
    def test_constructor_chain_not_in_constraints(
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
        assert (
            all_diags[0].element_name
            == "position<mv:define-lang.org:test_pos_init_chain_bad:/wrong>"
        )
        assert (
            all_diags[0].parent_name
            == "position<mv:define-lang.org:test_pos_init_chain_bad:/other>"
        )
        assert all_diags[0].location.line == 6
        assert all_diags[0].location.column == 48
        assert all_diags[0].location.end_line == 6
        assert all_diags[0].location.end_column == 64
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_valid_chain_past_implied_position(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_invalid_chain_past_implied_position(
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
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/z>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/x>"
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 44
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_valid_chain_past_implied_action_iface(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_invalid_chain_past_implied_action(
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
        assert all_diags[0].element_name == "position<not_iface>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/b>"
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 42
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_valid_three_element_chain_past_implied_position(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)


class TestMissingDefinitionInChain:
    def test_chained_name_with_missing_middle_definition(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
        assert all_diags[0].file_path == "middle.dfn"
        assert all_diags[0].location.line == 5
        assert all_diags[0].location.column == 33
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
