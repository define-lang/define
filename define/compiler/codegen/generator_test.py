# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.codegen import generator
from define.compiler.conftest import ValidateProject
from define.compiler.validator import validation_result


def _generate(
    program_result: validation_result.ProgramValidationResult,
) -> generator.GenerationResult:
    first_file = program_result.file_results[0]
    entry_file_definitions = [r.definition for r in first_file.definition_results]
    return generator.CodeGenerator().generate(
        program_result.reference_graph, entry_file_definitions
    )


class TestCodeGenerator:
    def test_position_entry_point_adds_no_diagnostics(
        self, validate_project: ValidateProject
    ):
        program_result = validate_project(
            {
                "test.def": "define the potential position<my.domain.com:my_lib:/test>.\n"
            },
        )

        gen_result = _generate(program_result)

        assert gen_result.diagnostics == []

    def test_action_entry_point_adds_diagnostic(
        self, validate_project: ValidateProject
    ):
        program_result = validate_project(
            {"test.def": "define the potential action<my.domain.com:my_lib:/test>.\n"},
        )

        gen_result = _generate(program_result)

        assert gen_result.code is None
        assert len(gen_result.diagnostics) == 1
        assert isinstance(
            gen_result.diagnostics[0], diagnostics.EntryPointNotPositionDiagnostic
        )
        assert gen_result.diagnostics[0].position.line == 1
        assert gen_result.diagnostics[0].position.column == 1

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
        gen_result = _generate(program_result)
        assert gen_result.code is not None
