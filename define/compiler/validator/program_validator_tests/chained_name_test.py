# pyright: reportUnusedCallResult=false
"""Chained position reference validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests.conftest import ValidateProject


class TestCreateDimensionPoint:
    def test_invalid_local_name_char(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "position<Bad>"
        assert diags[0].preceding_name == "position<inner_pos>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 58
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "position<Bad>"
        assert diags[1].parent_name == "position<inner_pos>"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 58
        assert isinstance(diags[2], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[2].local_name == "Bad"
        assert diags[2].char == "B"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 67

    def test_chain_both_endpoints_action(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 6
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_mid>"
        assert diags[2].preceding_name == "action<act_a>"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 52
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "action<act_b>"
        assert diags[3].preceding_name == "position<pos_mid>"
        assert diags[3].position.line == 6
        assert diags[3].position.column == 71
        assert isinstance(diags[4], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[4].position.line == 6
        assert diags[4].position.column == 71
        assert isinstance(diags[5], diagnostics.LocalActionNameDiagnostic)
        assert diags[5].local_name == "act_b"
        assert diags[5].position.line == 6
        assert diags[5].position.column == 78

    def test_chain_ending_with_action(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<act_b>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<act_b>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[2].position.line == 6
        assert diags[2].position.column == 54
        assert isinstance(diags[3], diagnostics.LocalActionNameDiagnostic)
        assert diags[3].local_name == "act_b"
        assert diags[3].position.line == 6
        assert diags[3].position.column == 61

    def test_chain_starting_with_action(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_b>"
        assert diags[2].preceding_name == "action<act_a>"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 52

    def test_local_action_name_does_not_match_position(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<a>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "a"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_b>"
        assert diags[2].preceding_name == "action<a>"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 48

    def test_name_error_with_chain_endpoint_check(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 44
        assert isinstance(
            diags[2], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[2].local_name == "position<pos_other>"
        assert diags[2].preceding_name == "action<Bad>"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 50

    def test_valid_chain_with_action_in_middle(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                "act_b.def": (
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
        assert not result.has_errors()

    def test_chain_second_element_not_in_constraints(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 5
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<wrong>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 10
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<wrong>"
        assert diags[1].position.line == 10
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "wrong"
        assert diags[2].position.line == 10
        assert diags[2].position.column == 61
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_end>"
        assert diags[3].preceding_name == "action<wrong>"
        assert diags[3].position.line == 10
        assert diags[3].position.column == 69
        assert isinstance(
            diags[4], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[4].universe == "my.domain.com:my_lib"
        assert diags[4].position.line == 4
        assert diags[4].position.column == 31

    def test_chain_second_element_global_not_in_constraints(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
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
                "correct.def": (
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
                "wrong.def": (
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
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<x>"

    def test_chain_second_element_position_has_no_constraints(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<act_b>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<act_b>"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 61
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].position.line == 6
        assert diags[3].position.column == 69

    def test_chain_second_element_matches_constraint(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
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
                "child.def": (
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
        assert not result.has_errors()

    def test_duplicate_definition_preserves_first_constraints(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
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
                "child.def": (
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
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert all_diags[0].local_name == "pos_a"
        assert all_diags[0].first_definition_line == 2
        assert all_diags[0].position.line == 7
        assert all_diags[0].position.column == 25

    def test_duplicate_source_definition_does_not_add_chain_diagnostics(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
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
                "child.def": (
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
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
        assert all_diags[0].definition_type == "action"
        assert all_diags[0].path == "/test"
        assert all_diags[0].first_definition_line == 1
        assert all_diags[0].position.line == 10
        assert all_diags[0].position.column == 1

    def test_chain_second_element_wrong_type_in_constraints(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 5
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<child>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 10
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<child>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 10
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "child"
        assert diags[2].position.line == 10
        assert diags[2].position.column == 61
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_end>"
        assert diags[3].preceding_name == "action<child>"
        assert diags[3].position.line == 10
        assert diags[3].position.column == 69
        assert isinstance(
            diags[4], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[4].universe == "my.domain.com:my_lib"
        assert diags[4].position.line == 4
        assert diags[4].position.column == 33

    def test_chain_second_element_skipped_when_first_undefined(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_such>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 46
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<no_such>"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 56
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 63
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].position.line == 6
        assert diags[3].position.column == 71

    def test_chain_second_element_name_error_also_not_in_constraints(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 5
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 10
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<Bad>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 10
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[2].local_name == "Bad"
        assert diags[2].char == "B"
        assert diags[2].position.line == 10
        assert diags[2].position.column == 61
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_end>"
        assert diags[3].preceding_name == "action<Bad>"
        assert diags[3].position.line == 10
        assert diags[3].position.column == 67
        assert isinstance(
            diags[4], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[4].universe == "my.domain.com:my_lib"
        assert diags[4].position.line == 4
        assert diags[4].position.column == 31

    def test_chained_local_after_short_form_global_position(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position</other>::position<local>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": "define the potential position<my.domain.com:my_lib:/other>.\n",
            },
        )
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert all_diags[0].local_name == "position<local>"
        assert all_diags[0].preceding_name == "position<my.domain.com:my_lib:/other>"

    def test_undefined_local_position_in_chain(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_pos>"
        assert diags[0].position.line == 6
        assert diags[0].position.column == 46
        assert isinstance(
            diags[1], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[1].local_name == "action<act_b>"
        assert diags[1].preceding_name == "position<no_pos>"
        assert diags[1].position.line == 6
        assert diags[1].position.column == 55
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].position.line == 6
        assert diags[2].position.column == 62
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<act_b>"
        assert diags[3].position.line == 6
        assert diags[3].position.column == 70

    def test_chain_third_element_in_position_constraints(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.def": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.def": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            }
        )
        assert not result.has_errors()

    def test_chain_third_element_not_in_position_constraints(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.def": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.def": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
                "wrong.def": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            }
        )
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].position.line == 10
        assert all_diags[0].position.column == 72

    def test_chain_third_element_position_no_constraints(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.def": "define the potential position<my.domain.com:my_lib:/pos_b>.\n",
                "pos_c.def": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            }
        )
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/pos_c>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].position.line == 10
        assert all_diags[0].position.column == 72

    def test_chain_element_inside_action_valid(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                "act_b.def": (
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
        assert not result.has_errors()

    def test_chain_element_inside_action_not_found(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
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
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].position.line == 10
        assert all_diags[0].position.column == 70

    def test_chain_element_inside_action_no_block(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
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
                "act_b.def": "define the potential action<my.domain.com:my_lib:/act_b>.\n",
            }
        )
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<pos_c>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].position.line == 10
        assert all_diags[0].position.column == 70

    def test_five_element_alternating_chain(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>::action</act_d>::position<pos_e>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pos_c> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_d>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_c> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_d.def": (
                    "define the potential action<my.domain.com:my_lib:/act_d> {\n"
                    "    define the position<pos_e>.\n"
                    "    it happens when {\n"
                    "        the position<pos_e> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        assert not result.has_errors()

    def test_four_element_chain_through_positions(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pos_a> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pos_a> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>::position</pos_d>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.def": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.def": (
                    "define the potential position<my.domain.com:my_lib:/pos_c> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</pos_d>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_d.def": "define the potential position<my.domain.com:my_lib:/pos_d>.\n",
            }
        )
        assert not result.has_errors()

    def test_chain_third_element_skipped_when_second_fails(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 5
        assert isinstance(
            diags[0], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[0].local_name == "action<wrong>"
        assert diags[0].preceding_name == "position<pos_a>"
        assert diags[0].position.line == 10
        assert diags[0].position.column == 54
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<wrong>"
        assert diags[1].position.line == 10
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "wrong"
        assert diags[2].position.line == 10
        assert diags[2].position.column == 61
        assert isinstance(
            diags[3], diagnostics.ChainedLocalNameRequiresActionDiagnostic
        )
        assert diags[3].local_name == "position<pos_c>"
        assert diags[3].preceding_name == "action<wrong>"
        assert diags[3].position.line == 10
        assert diags[3].position.column == 69
        assert isinstance(
            diags[4], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[4].universe == "my.domain.com:my_lib"
        assert diags[4].position.line == 4
        assert diags[4].position.column == 31

    def test_chain_action_cannot_contain_action(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</foo>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in"
                    " position<x>::action</foo>::action</bar>::position<y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "foo.def": (
                    "define the potential action<my.domain.com:my_lib:/foo> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "bar.def": (
                    "define the potential action<my.domain.com:my_lib:/bar> {\n"
                    "    define the position<y>.\n"
                    "    it happens when {\n"
                    "        the position<y> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            }
        )
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert [type(d) for d in test_result.diagnostics] == [
            diagnostics.ChainElementNotInActionDiagnostic,
        ]
        diag = test_result.diagnostics[0]
        assert isinstance(diag, diagnostics.ChainElementNotInActionDiagnostic)
        assert diag.element_name == "action<my.domain.com:my_lib:/bar>"
        assert diag.parent_name == "action<my.domain.com:my_lib:/foo>"
        assert diag.position.line == 10
        assert diag.position.column == 64

    def test_chain_action_then_action_short(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in"
                    " position<x>::action</a>::action</b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "a.def": (
                    "define the potential action<my.domain.com:my_lib:/a> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "b.def": "define the potential action<my.domain.com:my_lib:/b>.\n",
            }
        )
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert [type(d) for d in test_result.diagnostics] == [
            diagnostics.PositionReferenceChainEndDiagnostic,
            diagnostics.ChainElementNotInActionDiagnostic,
        ]
        end_diag = test_result.diagnostics[0]
        assert isinstance(end_diag, diagnostics.PositionReferenceChainEndDiagnostic)
        assert end_diag.position.line == 10
        assert end_diag.position.column == 62
        diag = test_result.diagnostics[1]
        assert isinstance(diag, diagnostics.ChainElementNotInActionDiagnostic)
        assert diag.element_name == "action<my.domain.com:my_lib:/b>"
        assert diag.parent_name == "action<my.domain.com:my_lib:/a>"
        assert diag.position.line == 10
        assert diag.position.column == 62


class TestMoveDimensionPoint:
    def test_chain_ending_with_action_in_from(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                    "        move the dimension point in position<pos_a>::action</act_b>"
                    " to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
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
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_chain_ending_with_action_in_to(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                    "        move the dimension point in position<pos_from>"
                    " to position<pos_a>::action</act_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
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
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_single_action_in_from_position(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<to_pos>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in action</act_x>"
                    " to position<to_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_x.def": (
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
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_single_action_in_to_position(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<from_pos>.\n"
                    "    it happens when {\n"
                    "        the position<from_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<from_pos>"
                    " to action</act_y>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_y.def": (
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
        test_result = next(
            r for r in result.file_results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_valid_chained_through_action(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                    "        create a dimension point in"
                    " position<pos_a>::action</act_middle>::position<inner_pos>.\n"
                    "        move the dimension point in"
                    " position<pos_a>::action</act_middle>::position<inner_pos>"
                    " to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_middle.def": (
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
        assert not result.has_errors()

    def test_chain_not_in_constraints(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
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
                    "        move the dimension point in"
                    " position<pos_a>::position</pos_b>::position</wrong>"
                    " to position<dest>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_b.def": (
                    "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</pos_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos_c.def": "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
                "wrong.def": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            }
        )
        all_diags = result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].position.column == 72


class TestUnnecessarySelfReference:
    def test_self_reference_in_chain(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert diags[0].definition_name == "action<my.domain.com:my_lib:/test>"
        assert diags[0].message == (
            "the reference to 'action<my.domain.com:my_lib:/test>' is not necessary"
            " because the code is already inside that definition"
        )

    def test_self_reference_still_validates_remaining_chain(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
        assert isinstance(diags[2], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[2].local_name == "Bad"

    def test_self_reference_removal_affects_downstream_validation(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UnnecessarySelfReferenceDiagnostic)
        assert isinstance(diags[1], diagnostics.LocalDuplicateDimensionPointDiagnostic)

    def test_single_element_self_reference_not_stripped(self):
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
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.PositionReferenceChainEndDiagnostic)
        assert isinstance(diags[1], diagnostics.CircularGlobalReferenceDiagnostic)


class TestChainActionValidation:
    def test_local_action_name_after_action_rejected(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<x>::action</a>::action<bad>.\n"
                    "    }\n"
                    "}\n"
                ),
                "a.def": (
                    "define the potential action<my.domain.com:my_lib:/a> {\n"
                    "    define the position<inner>.\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
            max_workers=1,
        )
        assert len(result.file_results) == 2
        assert result.file_results[0].file_path == PurePosixPath("test.def")
        assert result.file_results[1].file_path == PurePosixPath("a.def")
        assert list(result.file_results[1].diagnostics) == []
        assert len(result.file_results[0].diagnostics) == 3
        assert isinstance(
            result.file_results[0].diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )
        assert result.file_results[0].diagnostics[0].position.line == 10
        assert result.file_results[0].diagnostics[0].position.column == 62
        assert isinstance(
            result.file_results[0].diagnostics[1],
            diagnostics.ChainElementNotInActionDiagnostic,
        )
        assert result.file_results[0].diagnostics[1].element_name == "action<bad>"
        assert (
            result.file_results[0].diagnostics[1].parent_name
            == "action<my.domain.com:my_lib:/a>"
        )
        assert result.file_results[0].diagnostics[1].position.line == 10
        assert result.file_results[0].diagnostics[1].position.column == 62
        assert isinstance(
            result.file_results[0].diagnostics[2], diagnostics.LocalActionNameDiagnostic
        )
        assert result.file_results[0].diagnostics[2].local_name == "bad"

    def test_chain_through_action_with_constrained_local_position(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<x>::action</act>::position<inner>::position</wrong>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.def": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</allowed>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "allowed.def": "define the potential position<my.domain.com:my_lib:/allowed>.\n",
                "wrong.def": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            },
            max_workers=1,
        )
        assert len(result.file_results) == 4
        assert result.file_results[0].file_path == PurePosixPath("test.def")
        assert len(result.file_results[0].diagnostics) == 1
        diag = result.file_results[0].diagnostics[0]
        assert isinstance(diag, diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diag.element_name == "position<my.domain.com:my_lib:/wrong>"
        assert diag.parent_name == "position<inner>"
        assert diag.position.line == 10
        assert all(len(r.diagnostics) == 0 for r in result.file_results[1:])

    def test_chain_through_action_valid_continuation(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<x>::action</act>::position<inner>::position</deeper>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.def": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</deeper>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "deeper.def": "define the potential position<my.domain.com:my_lib:/deeper>.\n",
            },
            max_workers=1,
        )
        assert len(result.file_results) == 3
        assert all(len(r.diagnostics) == 0 for r in result.file_results)

    def test_deferred_chain_continuation_through_action_produces_error(
        self, validate_project: ValidateProject
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<x> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<x> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<x>::action</act>::position<inner>::position</target>::position</leaf>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act.def": (
                    "define the potential action<my.domain.com:my_lib:/act> {\n"
                    "    define the position<inner> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</target>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "target.def": (
                    "define the potential position<my.domain.com:my_lib:/target> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the position</allowed_leaf>.\n"
                    "    }\n"
                    "}\n"
                ),
                "leaf.def": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
                "allowed_leaf.def": "define the potential position<my.domain.com:my_lib:/allowed_leaf>.\n",
            },
            max_workers=1,
        )
        assert len(result.file_results) == 5
        assert result.file_results[0].file_path == PurePosixPath("test.def")
        assert len(result.file_results[0].diagnostics) == 1
        diag = result.file_results[0].diagnostics[0]
        assert isinstance(diag, diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diag.element_name == "position<my.domain.com:my_lib:/leaf>"
        assert diag.parent_name == "position<my.domain.com:my_lib:/target>"
        assert all(len(r.diagnostics) == 0 for r in result.file_results[1:])
