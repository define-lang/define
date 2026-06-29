# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def test_undefined_local_position_in_create():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        create a particle in position<undefined>.\n"
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
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<undefined>"
    assert diags[0].location.line == 5
    assert diags[0].location.column == 30


def test_empty_action_statements_block():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pp>.\n"
        "    it happens when {\n"
        "        the position<pp> has a particle.\n"
        "    } and it does {\n"
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
    assert isinstance(diags[0], diagnostics.EmptyActionStatementsBlockDiagnostic)
