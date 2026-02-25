from define.compiler import diagnostics, program_validator


def test_different_names_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "define the position<beta>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_duplicate_name_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21


def test_three_locals_two_same_one_diagnostic():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "define the position<beta>.\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].position.line == 4
    assert diags[0].position.column == 21


def test_three_same_name_two_diagnostics():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "define the position<alpha>.\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].position.line == 3
    assert diags[0].position.column == 21
    assert diags[1].local_name == "alpha"
    assert diags[1].first_definition_line == 2
    assert diags[1].position.line == 4
    assert diags[1].position.column == 21


def test_terminated_action_no_error():
    source = "define the potential action<my.domain.com:my_lib:/act>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_single_local_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_separate_actions_same_local_name_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_action_statements_local_name_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<alpha>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_action_statements_duplicate_name_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<alpha>.\n"
        "define the position<alpha>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 4
    assert diags[0].position.line == 5
    assert diags[0].position.column == 21


def test_action_statements_name_conflicts_with_parent_scope():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<alpha>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].position.line == 5
    assert diags[0].position.column == 21


def test_action_statements_two_duplicates_point_to_parent_scope_definition():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "define the position<alpha>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "define the position<alpha>.\n"
        "define the position<alpha>.\n"
        "}\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[1].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[1].first_definition_line == 2
    assert diags[0].position.line == 5
    assert diags[0].position.column == 21
    assert diags[1].position.line == 6
    assert diags[1].position.column == 21
