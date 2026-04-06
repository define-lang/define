# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def test_valid_destroy_in_action_body():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_target>.\n"
        "        destroy the dimension point in position<_target>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert diags == []


def test_valid_destroy_in_position_init_block():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        define the position<inner>.\n"
        "        destroy the dimension point in position<inner>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert diags == []


def test_undefined_local_position_in_destroy():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        destroy the dimension point in position<undefined>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)


def test_undefined_local_position_destroy_in_position_init_block():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        destroy the dimension point in position<undefined>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)


def test_non_self_ref_global_in_action_body():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        destroy the dimension point in action</other>::position<x>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[0].source_global_name == "action</other>"
    assert diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 40
    assert isinstance(
        diags[1], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[1].location.line == 6
    assert diags[1].location.column == 47


def test_non_self_ref_global_in_position_init():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        destroy the dimension point in action</other>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[0].source_global_name == "action</other>"
    assert diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 40
    assert isinstance(
        diags[1], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[1].location.line == 3
    assert diags[1].location.column == 47


def test_self_reference_destroy_in_position_init_is_valid():
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    after it is assigned {\n"
        "        destroy the dimension point in position</test>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert results[0].exception is None
    diags = results[0].diagnostics
    assert diags == []
