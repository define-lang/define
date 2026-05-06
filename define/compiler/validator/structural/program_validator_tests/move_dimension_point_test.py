from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.structural import program_validator


def test_move_from_a_position_to_itself():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 52
    assert diags[0].location.file_path is None
    assert diags[0].position_name == "position<a>"


def test_move_from_a_chained_position_to_itself(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x> to position<a>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<a>::position</x>"


def test_move_to_chained_prefix_position(validate_project: ValidateProject):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.dfn": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    test_result = next(
        r for r in result.file_results if r.file_path == PurePosixPath("test.dfn")
    )
    diags = test_result.diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 81
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].source_position == "position<local_pos>"
    assert diags[0].target_position == "position<local_pos>::position</target_pos>"
