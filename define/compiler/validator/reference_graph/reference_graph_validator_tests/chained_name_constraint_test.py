# pyright: reportUnusedCallResult=false
"""Chained position reference constraint-resolution tests."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestCreateDimensionPoint:
    def test_chain_second_element_not_in_constraints(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</other>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<wrong>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<wrong>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 54
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "wrong"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 61
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<wrong>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 69
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31

    def test_chain_second_element_global_not_in_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</correct>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<x>::action</wrong>::position<end>.\n"
                    "    }\n"
                    "}\n"
                ),
                "correct.dfn": (
                    "define the potential action<my.domain.com:my_lib:/correct> {\n"
                    "    define the position<end>.\n"
                    "    it happens when {\n"
                    "        the position<end> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "wrong.dfn": (
                    "define the potential action<my.domain.com:my_lib:/wrong> {\n"
                    "    define the position<end>.\n"
                    "    it happens when {\n"
                    "        the position<end> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<x>"
        assert all_diags[0].location.line == 10
        assert all_diags[0].location.column == 50
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_second_element_position_has_no_constraints(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<act_b>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 54
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_b"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 61
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_c>"
        assert diags[2].preceding_name == "action<act_b>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 69

    def test_chain_second_element_matches_constraint(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</child>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</child>::position<pos_end>.\n"
                    "    }\n"
                    "}\n"
                ),
                "child.dfn": (
                    "define the potential action<my.domain.com:my_lib:/child> {\n"
                    "    define the position<pos_end>.\n"
                    "    it happens when {\n"
                    "        the position<pos_end> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert_no_errors(result.program_result)

    def test_duplicate_definition_preserves_first_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</child>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<pos_a>.\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</child>::position<pos_end>.\n"
                    "    }\n"
                    "}\n"
                ),
                "child.dfn": (
                    "define the potential action<my.domain.com:my_lib:/child> {\n"
                    "    define the position<pos_end>.\n"
                    "    it happens when {\n"
                    "        the position<pos_end> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert all_diags[0].local_name == "pos_a"
        assert all_diags[0].first_definition_line == 2
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 25
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_duplicate_source_definition_does_not_add_chain_diagnostics(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</child>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</child>::position<no_such>.\n"
                    "    }\n"
                    "}\n"
                ),
                "child.dfn": (
                    "define the potential action<my.domain.com:my_lib:/child> {\n"
                    "    define the position<pos_end>.\n"
                    "    it happens when {\n"
                    "        the position<pos_end> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
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
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</child>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<child>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<child>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 54
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "child"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 61
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<child>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 69
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 33

    def test_chain_second_element_skipped_when_first_undefined(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<no_such>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_such>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 46
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<no_such>"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 56
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 63
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].location.line == 6
        assert diags[3].location.column == 71

    def test_chain_second_element_name_error_also_not_in_constraints(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</child>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<Bad>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 54
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 61
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_end>"
        assert diags[2].preceding_name == "action<Bad>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 67
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31

    def test_chain_third_element_skipped_when_second_fails(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</other>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<wrong>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<wrong>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].location.line == 10
        assert diags[0].location.column == 54
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "wrong"
        assert diags[1].location.line == 10
        assert diags[1].location.column == 61
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_c>"
        assert diags[2].preceding_name == "action<wrong>"
        assert diags[2].location.line == 10
        assert diags[2].location.column == 69
        assert isinstance(
            diags[3], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[3].universe == "my.domain.com:my_lib"
        assert diags[3].location.line == 4
        assert diags[3].location.column == 31
