# pyright: reportUnusedCallResult=false
"""Tests for the top-level code generator."""

from define.compiler import diagnostics
from define.compiler.codegen import generator
from define.compiler.conftest import ValidateProject


class TestCodeGenerator:
    def test_position_entry_point_adds_no_diagnostics(
        self, validate_project: ValidateProject
    ):
        program_result = validate_project(
            {
                "test.def": "define the potential position<my.domain.com:my_lib:/test>.\n"
            },
        )

        generator.CodeGenerator().generate(program_result)

        assert program_result.file_results[0].diagnostics == []

    def test_action_entry_point_adds_diagnostic(
        self, validate_project: ValidateProject
    ):
        program_result = validate_project(
            {"test.def": "define the potential action<my.domain.com:my_lib:/test>.\n"},
        )

        result = generator.CodeGenerator().generate(program_result)

        assert result is None
        file_diagnostics = program_result.file_results[0].diagnostics
        assert len(file_diagnostics) == 1
        assert isinstance(
            file_diagnostics[0], diagnostics.EntryPointNotPositionDiagnostic
        )
        assert file_diagnostics[0].position.line == 1
        assert file_diagnostics[0].position.column == 1

    def test_file_with_action_and_position_passes(
        self, validate_project: ValidateProject
    ):
        program_result = validate_project(
            {
                "test.def": "define the potential position<my.domain.com:my_lib:/test>.\n"
                + "define the potential action<my.domain.com:my_lib:/test>.\n",
            },
        )

        assert not program_result.has_errors()
        result = generator.CodeGenerator().generate(program_result)
        assert result is not None
