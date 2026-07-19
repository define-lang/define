# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator.structural import program_validator


def test_valid_local_position():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<my_pos>.\n"
        "    it happens when {\n"
        "        the position<my_pos> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert diags == []


def test_valid_destructor():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert diags == []


def test_valid_constructor():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert diags == []


def test_undefined_local_name(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<unknown>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 13


def test_action_type_in_trigger_condition_is_rejected(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 3
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "action<my_act>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 13
    assert isinstance(diags[1], diagnostics.LocalActionNameDiagnostic)
    assert diags[1].local_name == "my_act"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 13
    assert isinstance(diags[2], diagnostics.PositionReferenceChainEndDiagnostic)
    assert diags[2].location.line == 3
    assert diags[2].location.column == 13


def test_invalid_local_name_format(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<BAD>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 13
    assert diags[0].location.end_line == 3
    assert diags[0].location.end_column == 26
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[1].local_name == "BAD"
    assert diags[1].char == "B"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 22
    assert diags[1].location.end_line == 3
    assert diags[1].location.end_column == 25
    assert diags[1].location.file_path is None
