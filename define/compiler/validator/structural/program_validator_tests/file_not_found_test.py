# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics, exceptions
from define.compiler.conftest import (
    ParseAndValidateFile,
    ValidateProject,
    ValidateTestdataStructural,
)
from define.compiler.data_structures import define_path


def test_entrypoint_file_not_found(validate_project: ValidateProject):
    result = validate_project({}, entry_file="nonexistent.dfn")
    assert len(result.file_results) == 1
    assert isinstance(
        result.file_results[0].exception, exceptions.SourceFileNotFoundError
    )
    assert result.file_results[0].diagnostics == []


def test_referenced_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "missing.dfn"
    assert diag.location.line == 3
    assert diag.location.column == 29


def test_referenced_file_not_found_via_already_completed_target(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</missing>.\n"
                "        it has the position</target>.\n"
                "    }\n"
                "}\n"
            ),
            "target.dfn": (
                "define the potential position<my.domain.com:my_lib:/target> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</missing>.\n"
                "    }\n"
                "}\n"
            ),
        },
        max_workers=1,
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].file_path == "missing.dfn"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[1].diagnostics[0].file_path == "missing.dfn"


def test_referenced_file_not_found_for_two_definitions_in_same_file(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<local> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</missing>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<local> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 9
    assert diags[1].location.column == 33


def test_same_missing_file_referenced_as_two_types_in_one_definition(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</missing>.\n"
        "        it has the action</missing>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 27
