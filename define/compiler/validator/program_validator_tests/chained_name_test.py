# pyright: reportUnusedCallResult=false
"""Chained position reference validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


class TestCreateDimensionPoint:
    def test_invalid_local_name_char(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<inner_pos>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<inner_pos>::position<Bad>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[0].local_name == "Bad"
        assert diags[0].char == "B"
        assert diags[0].position.line == 5
        assert diags[0].position.column == 67
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "position<Bad>"
        assert diags[1].parent_name == "position<inner_pos>"
        assert diags[1].position.line == 5
        assert diags[1].position.column == 58

    def test_chain_both_endpoints_action(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in action<act_a>::position<pos_mid>::action<act_b>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 4
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].position.line == 4
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 44
        assert isinstance(diags[2], diagnostics.LocalActionNameDiagnostic)
        assert diags[2].local_name == "act_b"
        assert diags[2].position.line == 4
        assert diags[2].position.column == 78
        assert isinstance(diags[3], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[3].position.line == 4
        assert diags[3].position.column == 71

    def test_chain_ending_with_action(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<act_b>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "act_b"
        assert diags[0].position.line == 5
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<act_b>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 5
        assert diags[1].position.column == 54
        assert isinstance(diags[2], diagnostics.PositionReferenceChainEndDiagnostic)
        assert diags[2].position.line == 5
        assert diags[2].position.column == 54

    def test_chain_starting_with_action(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in action<act_a>::position<pos_b>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<act_a>"
        assert diags[0].position.line == 4
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_a"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 44

    def test_local_action_name_does_not_match_position(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<a>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in action<a>::position<pos_b>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<a>"
        assert diags[0].position.line == 5
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "a"
        assert diags[1].position.line == 5
        assert diags[1].position.column == 44

    def test_name_error_with_chain_endpoint_check(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in action<Bad>::position<pos_other>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "action<Bad>"
        assert diags[0].position.line == 4
        assert diags[0].position.column == 44
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "Bad"
        assert diags[1].char == "B"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 44

    def test_valid_chain_with_action_in_middle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_chain_second_element_not_in_constraints(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</other>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<wrong>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "wrong"
        assert diags[0].position.line == 9
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<wrong>"
        assert diags[1].position.line == 9
        assert diags[1].position.column == 54
        assert isinstance(
            diags[2], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[2].universe == "my.domain.com:my_lib"
        assert diags[2].position.line == 4
        assert diags[2].position.column == 31

    def test_chain_second_element_position_has_no_constraints(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "act_b"
        assert diags[0].position.line == 5
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<act_b>"
        assert diags[1].position.line == 5
        assert diags[1].position.column == 54

    def test_chain_second_element_matches_constraint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</child>::position<pos_end>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "child.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<pos_end>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_duplicate_definition_preserves_first_constraints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</child>.\n"
                "        }\n"
                "    }\n"
                "    define the position<pos_a>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</child>::position<pos_end>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "child.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<pos_end>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert all_diags[0].local_name == "pos_a"
        assert all_diags[0].first_definition_line == 2
        assert all_diags[0].position.line == 7
        assert all_diags[0].position.column == 25

    def test_chain_second_element_wrong_type_in_constraints(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</child>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<child>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "child"
        assert diags[0].position.line == 9
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<child>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 9
        assert diags[1].position.column == 54
        assert isinstance(
            diags[2], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[2].universe == "my.domain.com:my_lib"
        assert diags[2].position.line == 4
        assert diags[2].position.column == 33

    def test_chain_second_element_skipped_when_first_undefined(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<no_such>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_such>"
        assert diags[0].position.line == 4
        assert diags[0].position.column == 46
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_b"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 63

    def test_chain_second_element_name_error_also_not_in_constraints(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</child>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<Bad>::position<pos_end>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[0].local_name == "Bad"
        assert diags[0].char == "B"
        assert diags[0].position.line == 9
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].element_name == "action<Bad>"
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].position.line == 9
        assert diags[1].position.column == 54
        assert isinstance(
            diags[2], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[2].universe == "my.domain.com:my_lib"
        assert diags[2].position.line == 4
        assert diags[2].position.column == 31

    def test_undefined_local_position_in_chain(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<no_pos>::action<act_b>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<no_pos>"
        assert diags[0].position.line == 4
        assert diags[0].position.column == 46
        assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
        assert diags[1].local_name == "act_b"
        assert diags[1].position.line == 4
        assert diags[1].position.column == 62

    def test_chain_third_element_in_position_constraints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_b.def").write_text(
            (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_c.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_chain_third_element_not_in_position_constraints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_b.def").write_text(
            (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_c.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            encoding="utf-8",
        )
        (tmp_path / "wrong.def").write_text(
            "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/wrong>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].position.line == 9
        assert all_diags[0].position.column == 72

    def test_chain_third_element_position_no_constraints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_b.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_b>.\n",
            encoding="utf-8",
        )
        (tmp_path / "pos_c.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].element_name == "position<my.domain.com:my_lib:/pos_c>"
        assert all_diags[0].parent_name == "position<my.domain.com:my_lib:/pos_b>"
        assert all_diags[0].position.line == 9
        assert all_diags[0].position.column == 72

    def test_chain_element_inside_action_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_chain_element_inside_action_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<no_such>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].position.line == 9
        assert all_diags[0].position.column == 70

    def test_chain_element_inside_action_no_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            "define the potential action<my.domain.com:my_lib:/act_b>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
        assert all_diags[0].element_name == "position<pos_c>"
        assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/act_b>"
        assert all_diags[0].position.line == 9
        assert all_diags[0].position.column == 70

    def test_five_element_alternating_chain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::action</act_b>::position<pos_c>::action</act_d>::position<pos_e>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_d>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_d.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_d> {\n"
                "    define the position<pos_e>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_four_element_chain_through_positions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::position</pos_b>::position</pos_c>::position</pos_d>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_b.def").write_text(
            (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_c.def").write_text(
            (
                "define the potential position<my.domain.com:my_lib:/pos_c> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_d>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_d.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_d>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_chain_third_element_skipped_when_second_fails(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<pos_a> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</other>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<pos_a>::action<wrong>::position<pos_c>.\n"
            "    }\n"
            "}\n"
        )
        results = program_validator.ProgramValidator().validate_program_non_filesystem(
            source
        )
        diags = results[0].diagnostics
        assert len(diags) == 3
        assert isinstance(diags[0], diagnostics.LocalActionNameDiagnostic)
        assert diags[0].local_name == "wrong"
        assert diags[0].position.line == 9
        assert diags[0].position.column == 61
        assert isinstance(diags[1], diagnostics.ChainElementNotInConstraintsDiagnostic)
        assert diags[1].parent_name == "position<pos_a>"
        assert diags[1].element_name == "action<wrong>"
        assert diags[1].position.line == 9
        assert diags[1].position.column == 54
        assert isinstance(
            diags[2], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
        )
        assert diags[2].universe == "my.domain.com:my_lib"
        assert diags[2].position.line == 4
        assert diags[2].position.column == 31

    def test_chain_action_cannot_contain_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<x> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</foo>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in"
                " position<x>::action</foo>::action</bar>::position<y>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "foo.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<inner>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "bar.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/bar> {\n"
                "    define the position<y>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert [type(d) for d in test_result.diagnostics] == [
            diagnostics.ChainElementNotInActionDiagnostic,
        ]
        diag = test_result.diagnostics[0]
        assert isinstance(diag, diagnostics.ChainElementNotInActionDiagnostic)
        assert diag.element_name == "action<my.domain.com:my_lib:/bar>"
        assert diag.parent_name == "action<my.domain.com:my_lib:/foo>"
        assert diag.position.line == 9
        assert diag.position.column == 64

    def test_chain_action_then_action_short(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<x> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in"
                " position<x>::action</a>::action</b>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "a.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<inner>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "b.def").write_text(
            "define the potential action<my.domain.com:my_lib:/b>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert [type(d) for d in test_result.diagnostics] == [
            diagnostics.PositionReferenceChainEndDiagnostic,
            diagnostics.ChainElementNotInActionDiagnostic,
        ]
        end_diag = test_result.diagnostics[0]
        assert isinstance(end_diag, diagnostics.PositionReferenceChainEndDiagnostic)
        assert end_diag.position.line == 9
        assert end_diag.position.column == 62
        diag = test_result.diagnostics[1]
        assert isinstance(diag, diagnostics.ChainElementNotInActionDiagnostic)
        assert diag.element_name == "action<my.domain.com:my_lib:/b>"
        assert diag.parent_name == "action<my.domain.com:my_lib:/a>"
        assert diag.position.line == 9
        assert diag.position.column == 62


class TestMoveDimensionPoint:
    def test_chain_ending_with_action_in_from(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        move the dimension point in position<pos_a>::action</act_b>"
                " to position<pos_a>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_chain_ending_with_action_in_to(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        move the dimension point in position<pos_a>"
                " to position<pos_a>::action</act_b>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_b.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_single_action_in_from_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<to_pos>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        move the dimension point in action</act_x>"
                " to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_x.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_x> {\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_single_action_in_to_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos>"
                " to action</act_y>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_y.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_y> {\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        test_result = next(
            r for r in results if r.file_path == PurePosixPath("test.def")
        )
        assert len(test_result.diagnostics) == 1
        assert isinstance(
            test_result.diagnostics[0],
            diagnostics.PositionReferenceChainEndDiagnostic,
        )

    def test_valid_chained_through_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        create a dimension point in"
                " position<pos_a>::action</act_middle>::position<inner_pos>.\n"
                "        move the dimension point in"
                " position<pos_a>::action</act_middle>::position<inner_pos>"
                " to position<pos_a>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "act_middle.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/act_middle> {\n"
                "    define the position<inner_pos>.\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert all_diags == []

    def test_chain_not_in_constraints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        (tmp_path / "test.def").write_text(
            (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "    } and it does {\n"
                "        move the dimension point in"
                " position<pos_a>::position</pos_b>::position</wrong>"
                " to position<pos_a>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_b.def").write_text(
            (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "pos_c.def").write_text(
            "define the potential position<my.domain.com:my_lib:/pos_c>.\n",
            encoding="utf-8",
        )
        (tmp_path / "wrong.def").write_text(
            "define the potential position<my.domain.com:my_lib:/wrong>.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        results = program_validator.ProgramValidator().validate_program(
            PurePosixPath("test.def")
        )
        all_diags = [d for r in results for d in r.diagnostics]
        assert len(all_diags) == 1
        assert isinstance(
            all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic
        )
        assert all_diags[0].position.column == 62
