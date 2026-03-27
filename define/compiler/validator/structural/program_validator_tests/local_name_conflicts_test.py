"""Local name conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def test_different_names_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    define the position<beta>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_duplicate_name_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
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
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_three_locals_two_same_one_diagnostic():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    define the position<beta>.\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
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
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25


def test_three_same_name_two_diagnostics():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    define the position<alpha>.\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert diags[1].local_name == "alpha"
    assert diags[1].first_definition_line == 2
    assert diags[1].location.line == 4
    assert diags[1].location.column == 25


def test_terminated_action_no_error():
    source = "define the potential action<my.domain.com:my_lib:/act>.\n"
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_single_local_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_separate_actions_same_local_name_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_action_statements_local_name_no_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<alpha>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 0


def test_action_statements_duplicate_name_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<alpha>.\n"
        "        define the position<alpha>.\n"
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
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 6
    assert diags[0].location.line == 7
    assert diags[0].location.column == 29


def test_action_statements_name_conflicts_with_parent_scope():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<alpha>.\n"
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
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[0].location.line == 6
    assert diags[0].location.column == 29


def test_action_statements_two_duplicates_point_to_parent_scope_definition():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<alpha>.\n"
        "    it happens when {\n"
        "        the position<alpha> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<alpha>.\n"
        "        define the position<alpha>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
    assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
    assert diags[0].local_name == "alpha"
    assert diags[1].local_name == "alpha"
    assert diags[0].first_definition_line == 2
    assert diags[1].first_definition_line == 2
    assert diags[0].location.line == 6
    assert diags[0].location.column == 29
    assert diags[1].location.line == 7
    assert diags[1].location.column == 29
