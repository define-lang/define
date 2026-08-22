# pyright: reportUnusedCallResult=false
"""Chained position reference constraint-resolution tests."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


class TestCreateParticle:
    def test_chain_second_element_not_in_constraints(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "wrong"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 47
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<wrong>"
        assert diags[1].preceding_name == "position<pos_a>"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 47
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<wrong>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 62
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31

    def test_chain_second_element_global_not_in_constraints(
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
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<x>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 43
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_second_element_position_has_no_constraints(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "act_b"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 47
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<pos_a>"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 47
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_c>"
        assert diags[2].preceding_name == "action<act_b>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 62

    def test_chain_second_element_matches_constraint(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert_no_errors(result.program_result)

    def test_duplicate_definition_preserves_first_constraints(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert all_diags[0].local_name == "pos_a"
        assert all_diags[0].first_definition_line == 2
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 25
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_duplicate_source_definition_does_not_add_chain_diagnostics(
        self,
        validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
    ):
        result = validate_testdata_project_with_reference_graph()
        assert result.program_result.all_exceptions == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
        assert all_diags[0].definition_type == "action"
        assert all_diags[0].path == "/test"
        assert all_diags[0].first_definition_line == 1
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 1
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_second_element_wrong_type_in_constraints(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "child"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 47
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<child>"
        assert diags[1].preceding_name == "position<pos_a>"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 47
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<child>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 62
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 33

    def test_chain_second_element_skipped_when_first_undefined(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_such>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 30
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_b"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 49
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "action<act_b>"
        assert diags[2].preceding_name == "position<no_such>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 49
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].location.line == 6
        assert diags[3].location.column == 64

    def test_chain_second_element_name_error_also_not_in_constraints(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 47
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 54
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<Bad>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 60
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31

    def test_chain_third_element_skipped_when_second_fails(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        results = result.file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "wrong"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 47
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<wrong>"
        assert diags[1].preceding_name == "position<pos_a>"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 47
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_c>"
        assert diags[2].preceding_name == "action<wrong>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 62
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31
