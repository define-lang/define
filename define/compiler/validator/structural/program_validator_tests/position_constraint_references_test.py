# pyright: reportUnusedCallResult=false
"""Position constraint reference validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.structural import program_validator


def test_position_constraint_reference_with_invalid_path():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</Bad>.\n"
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
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Bad"
    assert diags[0].char == "B"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 30


def test_global_position_validates_constraints_block_before_initialization_block():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</BadConstraint>.\n"
        "    }\n"
        "    after it is assigned {\n"
        "        create a particle in position</BadInit>.\n"
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
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "BadConstraint"
    assert diags[0].location.line == 3
    assert isinstance(diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[1].location.line == 6
    assert isinstance(diags[2], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[2].segment == "BadInit"
    assert diags[2].location.line == 6


def test_same_fqun_constraint_reference_must_use_short_form():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<my.domain.com:my_lib:/child>.\n"
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
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_same_fqun_constraint_reference_in_local_position_must_use_short_form():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<my_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the position<my.domain.com:my_lib:/child>.\n"
        "        }\n"
        "    }\n"
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
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 33


def test_invalid_constraint_does_not_skip_remaining_constraints(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</Bad>.\n"
                "        it has the position</valid>.\n"
                "    }\n"
                "}\n"
            ),
            "valid.dfn": "define the potential position<my.domain.com:my_lib:/valid>.\n",
        }
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Bad"
    assert diags[0].char == "B"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 30
    assert result.file_results[1].file_path == PurePosixPath("valid.dfn")
    assert result.file_results[1].diagnostics == []


def test_referenced_global_name_wrong_type_position(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "target.dfn": (
                "define the potential action<mv:define-lang.org:test_walk_wrong_type:/target> {\n"
                "    define the position<_noop>.\n"
                "    it happens when {\n"
                "        the position<_noop> has a particle.\n"
                "    } and it does {\n"
                "        define the position<__noop>.\n"
                "        create a particle in position<__noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<mv:define-lang.org:test_walk_wrong_type:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</target>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name="mv:define-lang.org:test_walk_wrong_type",
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diags[0].path == "/target"
    assert diags[0].expected_type == "position"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29


def test_referenced_global_name_wrong_type_for_two_definitions_in_same_file(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "target.dfn": (
                "define the potential action<mv:define-lang.org:test_walk_wrong_type:/target> {\n"
                "    define the position<_noop>.\n"
                "    it happens when {\n"
                "        the position<_noop> has a particle.\n"
                "    } and it does {\n"
                "        define the position<__noop>.\n"
                "        create a particle in position<__noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<mv:define-lang.org:test_walk_wrong_type:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</target>.\n"
                "    }\n"
                "}\n"
                "define the potential action<mv:define-lang.org:test_walk_wrong_type:/test> {\n"
                "    define the position<local> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</target>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name="mv:define-lang.org:test_walk_wrong_type",
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diags[0].path == "/target"
    assert diags[0].expected_type == "position"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].path == "/target"
    assert diags[1].expected_type == "position"
    assert diags[1].location.line == 9
    assert diags[1].location.column == 33
