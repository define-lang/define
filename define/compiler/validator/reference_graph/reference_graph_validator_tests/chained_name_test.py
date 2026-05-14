# pyright: reportUnusedCallResult=false
"""Chained position reference structural-rule and move-operation tests."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestCreateDimensionPoint:
    def test_invalid_local_name_char(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<inner_pos>.\n"
            "    it happens when {\n"
            "        the position<inner_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<inner_pos>::position<Bad>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "position<Bad>"
        assert diags[0].preceding_name == "position<inner_pos>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 58
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 67

    def test_chain_both_endpoints_action(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action<act_a>::position<pos_mid>::action<act_b>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 6
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_mid>"
        assert diags[2].preceding_name == "action<act_a>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 52
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "action<act_b>"
        assert diags[3].preceding_name == "position<pos_mid>"
        assert diags[3].location.line == 6
        assert diags[3].location.column == 71
        assert isinstance(diags[4], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[4].location.line == 6
        assert diags[4].location.column == 71
        assert isinstance(diags[5], diagnostics.LocalActionNameDiagnostic)
        assert diags[5].local_name == "act_b"
        assert diags[5].location.line == 6
        assert diags[5].location.column == 78

    def test_chain_ending_with_action(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<act_b>.\n"
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
        assert isinstance(diags[1], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[1].location.line == 6
        assert diags[1].location.column == 54
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 61

    def test_chain_starting_with_action(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action<act_a>::position<pos_b>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_b>"
        assert diags[2].preceding_name == "action<act_a>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 52

    def test_local_action_name_does_not_match_position(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<a>.\n"
            "    it happens when {\n"
            "        the position<a> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action<a>::position<pos_b>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<a>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "a"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_b>"
        assert diags[2].preceding_name == "action<a>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 48

    def test_name_error_with_chain_endpoint_check(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action<Bad>::position<pos_other>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 44
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_other>"
        assert diags[2].preceding_name == "action<Bad>"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 50

    def test_valid_chain_with_action_in_middle(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pos_c>.\n"
                    "    it happens when {\n"
                    "        the position<pos_c> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert_no_errors(result.program_result)

    def test_chained_local_after_short_form_global_position(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position</other>::position<local>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "position</other>"
        assert all_diags[0].full_global_name == "position<my.domain.com:my_lib:/other>"
        assert all_diags[0].location.line == 6
        assert all_diags[0].location.column == 37
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(
            all_diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert all_diags[1].local_name == "position<local>"
        assert all_diags[1].preceding_name == "position<my.domain.com:my_lib:/other>"
        assert all_diags[1].location.line == 6
        assert all_diags[1].location.column == 55
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")

    def test_undefined_local_position_in_chain(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<no_pos>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_pos>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 46
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<no_pos>"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 55
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 62
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].location.line == 6
        assert diags[3].location.column == 70


class TestMoveDimensionPoint:
    def test_chain_ending_with_action_in_from(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<dest>.\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<pos_a>::action</act_b> to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
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
        assert isinstance(all_diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[0].location.line == 11
        assert all_diags[0].location.column == 54
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_chain_ending_with_action_in_to(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<pos_from>.\n"
                    "    it happens when {\n"
                    "        the position<pos_from> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<pos_from> to position<pos_a>::action</act_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
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
        assert isinstance(all_diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[0].location.line == 11
        assert all_diags[0].location.column == 76
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_single_action_in_from_position(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<to_pos>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in action</act_x> to position<to_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_x.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_x> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "action</act_x>"
        assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/act_x>"
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 37
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(all_diags[1], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[1].location.line == 7
        assert all_diags[1].location.column == 37
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")

    def test_single_action_in_to_position(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<from_pos>.\n"
                    "    it happens when {\n"
                    "        the position<from_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<from_pos> to action</act_y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_y.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_y> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "action</act_y>"
        assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/act_y>"
        assert all_diags[0].location.line == 6
        assert all_diags[0].location.column == 59
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(all_diags[1], diagnostics.PositionReferenceChainEndDiagnostic)
        assert all_diags[1].location.line == 6
        assert all_diags[1].location.column == 59
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")

    def test_valid_chained_through_action(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_middle>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<dest>.\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</act_middle>::position<inner_pos>.\n"
                    "        move the dimension point in position<pos_a>::action</act_middle>::position<inner_pos> to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_middle.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_middle> {\n"
                    "    define the position<inner_pos>.\n"
                    "    it happens when {\n"
                    "        the position<inner_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert_no_errors(result.program_result)

    def test_chain_not_in_constraints(
        self, validate_project_with_reference_graph: ValidateProjectWithReferenceGraph
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<dest>.\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<pos_a>::position</pos_b>::position</wrong> to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain dimension points where {\n"
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
        assert all_diags[0].location.line == 11
        assert all_diags[0].location.column == 72
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


class TestDestroyDimensionPoint:
    def test_undefined_local_position_in_chain(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        destroy the dimension point in position<no_pos>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_pos>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 49
        assert diags[0].location.file_path is None
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<no_pos>"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 58
        assert diags[1].location.file_path is None
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 65
        assert diags[2].location.file_path is None
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].location.line == 6
        assert diags[3].location.column == 73
        assert diags[3].location.file_path is None
