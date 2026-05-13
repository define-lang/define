# pyright: reportUnusedCallResult=false
"""Chained reference tests for self-references and atypical chain starts."""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestUnnecessarySelfReference:
    def test_self_reference_in_chain(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<inner>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</test>::position<inner>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 7
        assert diags[0].location.column == 37
        assert diags[0].message == (
            "the reference to 'action<my.domain.com:my_lib:/test>' is not necessary"
            " because the code is already inside that definition"
        )

    def test_self_reference_still_validates_remaining_chain(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<inner>.\n"
            "    it happens when {\n"
            "        the position<inner> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</test>::position<Bad>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 6
        assert diags[0].location.column == 37
        assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[1].local_name == "position<Bad>"
        assert diags[1].location.line == 6
        assert diags[1].location.column == 61
        assert isinstance(diags[2], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[2].local_name == "Bad"
        assert diags[2].char == "B"
        assert diags[2].location.line == 6
        assert diags[2].location.column == 61

    def test_self_reference_removal_affects_downstream_validation(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<trigger_pos>.\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<inner>.\n"
            "        create a dimension point in action</test>::position<inner>.\n"
            "        create a dimension point in position<inner>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].location.line == 7
        assert diags[0].location.column == 37
        assert isinstance(diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
        assert diags[1].position_name == "position<inner>"
        assert diags[1].location.line == 8
        assert diags[1].location.column == 37
        assert diags[1].populated_at.line == 7
        assert diags[1].populated_at.column == 37

    def test_single_element_self_reference_not_stripped(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<trigger_pos>.\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</test>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[0].location.line == 6
        assert diags[0].location.column == 37
        assert isinstance(diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
        assert diags[1].location.line == 6
        assert diags[1].location.column == 37
        assert diags[1].cycle == [
            "action<my.domain.com:my_lib:/test>",
            "action<my.domain.com:my_lib:/test>",
        ]


class TestUnknownGlobalChainStart:
    def test_no_constraint_check_on_unknown_global(
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
                    "        create a dimension point in action</other>::position<x>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<x>.\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
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
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "action</other>"
        assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
        assert all_diags[0].location.line == 6
        assert all_diags[0].location.column == 37
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")


class TestImpliedQualityChainStart:
    def test_valid_chain_past_implied_position(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
                "x.dfn": (
                    "define the potential position<my.domain.com:my_lib:/x> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it also assigns the position</x>.\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position</x>::position</y>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)

    def test_invalid_chain_past_implied_position(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "z.dfn": "define the potential position<my.domain.com:my_lib:/z>.\n",
                "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it also assigns the position</x>.\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position</x>::position</z>.\n"
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
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/z>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/x>"
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 51
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_valid_chain_past_implied_action_iface(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/b> {\n"
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
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it also assigns the action</b>.\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</b>::position<iface>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)

    def test_invalid_chain_past_implied_action(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/b> {\n"
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
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it also assigns the action</b>.\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</b>::position<not_iface>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<not_iface>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/b>"
        assert all_diags[0].location.line == 7
        assert all_diags[0].location.column == 49
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")

    def test_valid_three_element_chain_past_implied_position(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "z.dfn": "define the potential position<my.domain.com:my_lib:/z>.\n",
                "y.dfn": (
                    "define the potential position<my.domain.com:my_lib:/y> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</z>.\n"
                    "    }\n"
                    "}\n"
                ),
                "x.dfn": (
                    "define the potential position<my.domain.com:my_lib:/x> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it also assigns the position</x>.\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position</x>::position</y>::position</z>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)


class TestMissingDefinitionInChain:
    def test_chained_name_with_missing_middle_definition(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</middle>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>::position</middle>::position</end>.\n"
                    "    }\n"
                    "}\n"
                ),
                "end.dfn": "define the potential position<my.domain.com:my_lib:/end>.\n",
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
        assert all_diags[0].file_path == "middle.dfn"
        assert all_diags[0].location.line == 5
        assert all_diags[0].location.column == 33
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert isinstance(all_diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
        assert all_diags[1].file_path == "middle.dfn"
        assert all_diags[1].location.line == 11
        assert all_diags[1].location.column == 65
        assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
