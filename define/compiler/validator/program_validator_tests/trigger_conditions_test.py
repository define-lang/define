# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator import program_validator


class TestTriggerConditionValidation:
    def test_valid_local_name(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<my_pos>.\n"
            "    it happens when {\n"
            "        the position<my_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        results = (
            program_validator.ProgramValidator()
            .validate_program_non_filesystem(source)
            .file_results
        )
        diags = results[0].diagnostics
        assert diags == []

    def test_undefined_local_name(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "        the position<unknown> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
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
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<unknown>"
        assert diags[0].position.line == 3
        assert diags[0].position.column == 22

    def test_valid_global_name(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    it happens when {\n"
                    "        the position</other> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": "define the potential position<my.domain.com:my_lib:/other>.\n",
            }
        )
        assert not result.has_errors()

    def test_invalid_local_name_format(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "        the position<BAD> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
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
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<BAD>"
        assert diags[0].position.line == 3
        assert diags[0].position.column == 22
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "BAD"
        assert diags[1].char == "B"
        assert diags[1].position.line == 3
        assert diags[1].position.column == 22

    def test_two_item_chain(self, validate_project: ValidateProject):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<my_pos> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the position</inner>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<my_pos>::position</inner> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "inner.def": "define the potential position<my.domain.com:my_lib:/inner>.\n",
            }
        )
        assert not result.has_errors()

    def test_chain_ending_with_action(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "        the position<pos_a>::action<act_b> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
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
        assert diags[0].position.line == 4
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<act_b>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 30
        assert isinstance(diags[2], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[2].position.line == 4
        assert diags[2].position.column == 30
        assert isinstance(diags[3], diagnostics.LocalActionNameDiagnostic)
        assert diags[3].local_name == "act_b"
        assert diags[3].position.line == 4
        assert diags[3].position.column == 37

    def test_three_item_chain_valid(self, validate_project: ValidateProject):
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
                    "        the position<pos_a>::position</pos_b>::position</pos_c> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
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

    def test_three_item_chain_invalid(self, validate_project: ValidateProject):
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
                    "        the position<pos_a>::position</pos_b>::position</wrong> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
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
        assert all_diags[0].position.line == 8
        assert all_diags[0].position.column == 48
