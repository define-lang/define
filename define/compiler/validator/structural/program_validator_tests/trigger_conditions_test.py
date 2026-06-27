# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
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


def test_undefined_local_name():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        the position<unknown> has a particle.\n"
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
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<unknown>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 13


def test_action_type_in_trigger_condition_is_rejected():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        the action<my_act> has a particle.\n"
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
