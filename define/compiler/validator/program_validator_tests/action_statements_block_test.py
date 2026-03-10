# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.validator import program_validator


def test_empty_position_init_block():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.EmptyPositionInitBlockDiagnostic)


def test_empty_action_statements_block():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pp>.\n"
        "    it happens when {\n"
        "        the position<pp> has a dimension point.\n"
        "    } and it does {\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.EmptyActionStatementsBlockDiagnostic)
