# pyright: reportUnusedCallResult=false

from pathlib import Path

from define.compiler import diagnostics
from define.compiler.codegen import generator
from define.compiler.conftest import ValidateProject
from define.compiler.validator import validation_result
from define.compiler.validator.test_helpers import assert_no_errors


def _generate(
    program_result: validation_result.ProgramValidationResult,
    tmp_path: Path,
) -> list[diagnostics.Diagnostic]:
    first_file = program_result.file_results[0]
    entry_file_definitions = [r.definition for r in first_file.definition_results]
    return generator.CodeGenerator().generate(
        program_result.reference_graph, entry_file_definitions, tmp_path
    )


class TestCodeGenerator:
    def test_position_entry_point_adds_no_diagnostics(
        self, validate_project: ValidateProject, tmp_path: Path
    ):
        program_result = validate_project(
            {
                "test.dfn": "define the potential position<my.domain.com:my_lib:/test>.\n"
            },
        )

        result = _generate(program_result, tmp_path)

        assert result == []

    def test_action_entry_point_adds_diagnostic(
        self, validate_project: ValidateProject, tmp_path: Path
    ):
        program_result = validate_project(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pp>.\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<noop>.\n"
                    "        create a particle in position<noop>.\n"
                    "    }\n"
                    "}\n"
                )
            },
        )

        result = _generate(program_result, tmp_path)

        assert len(result) == 1
        assert isinstance(result[0], diagnostics.EntryPointNotPositionDiagnostic)
        assert result[0].location.line == 1
        assert result[0].location.column == 1

    def test_file_with_action_and_position_passes(
        self, validate_project: ValidateProject, tmp_path: Path
    ):
        program_result = validate_project(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test>.\n"
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<pp>.\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<noop>.\n"
                    "        create a particle in position<noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )

        assert_no_errors(program_result)
        assert _generate(program_result, tmp_path) == []
        main_file = tmp_path / "__main__.py"
        assert main_file.exists()
        assert main_file.stat().st_size > 0
