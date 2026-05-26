# pyright: reportUnusedCallResult=false
"""Quality Implication Statement validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateProject,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors


def test_non_self_ref_global_in_action_body(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</other>::position<x>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<x>.\n"
                "    it happens when {\n"
                "        the position<x> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37


def test_non_self_ref_global_in_position_init(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 3
    assert all_diags[0].location.column == 37


def test_constraint_does_not_make_global_available_as_chain_start(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 37


def test_self_reference_in_position_init_is_valid(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert_action_calls(
        result.action_call_graph,
        "position<my.domain.com:my_lib:/test>",
        "action<my.domain.com:my_lib:/other>",
    )


def test_two_distinct_used_quality_implication_statements():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/bar>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</bar>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
        "        create a dimension point in position</bar>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)


def test_action_implication_used_via_interface_position_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/foo> {\n"
        "    define the position<x>.\n"
        "    it happens when {\n"
        "        the position<x> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the action</foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in action</foo>::position<x>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)


def test_position_implication_used_only_via_implied_position_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/bar> {\n"
        "    define the position<x>.\n"
        "    it happens when {\n"
        "        the position<x> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/foo> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the action</bar>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>::action</bar>::position<x>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert_no_errors(result)


def test_global_used_without_implication_is_unknown():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[0].source_global_name == "position</foo>"
    assert diags[0].full_global_name == "position<my.domain.com:my_lib:/foo>"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 37


def test_duplicate_implication_in_global_position_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].first_implication_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25


def test_duplicate_implication_in_action_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</foo>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].first_implication_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25


def test_three_duplicate_implication_two_errors():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert isinstance(diags[1], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].first_implication_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25
    assert diags[1].implication_name == "position</foo>"
    assert diags[1].first_implication_line == 3
    assert diags[1].location.line == 5
    assert diags[1].location.column == 25


def test_duplicate_implication_full_fqun_cross_universe(
    validate_project: ValidateProject,
):
    implier_fqun = "mv:define-lang.org:implier_dup_implication"
    implied_fqun = "mv:define-lang.org:implied_dup_implication"
    result = validate_project(
        {
            "test.dfn": (
                f"define the potential position<{implier_fqun}:/test> {{\n"
                f"    it also assigns the position<{implied_fqun}:/foo>.\n"
                f"    it also assigns the position<{implied_fqun}:/foo>.\n"
                "    after it is assigned {\n"
                f"        create a dimension point in position<{implied_fqun}:/foo>.\n"
                "    }\n"
                "}\n"
            ),
            "lib/foo.dfn": f"define the potential position<{implied_fqun}:/foo>.\n",
        },
        universe_name=implier_fqun,
        local_deps={implied_fqun: "lib"},
        sub_roots={"lib": implied_fqun},
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == f"position<{implied_fqun}:/foo>"
    assert diags[0].first_implication_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert result.file_results[1].file_path == PurePosixPath("lib/foo.dfn")
    assert result.file_results[1].diagnostics == []


def test_implication_same_path_different_fquns_are_not_duplicates(
    validate_project: ValidateProject,
):
    main_fqun = "mv:define-lang.org:implication_distinct_main"
    a_fqun = "mv:define-lang.org:implication_distinct_lib_a"
    b_fqun = "mv:define-lang.org:implication_distinct_lib_b"
    result = validate_project(
        {
            "a/foo.dfn": f"define the potential position<{a_fqun}:/foo>.\n",
            "b/foo.dfn": f"define the potential position<{b_fqun}:/foo>.\n",
            "test.dfn": (
                f"define the potential position<{main_fqun}:/test> {{\n"
                f"    it also assigns the position<{a_fqun}:/foo>.\n"
                f"    it also assigns the position<{b_fqun}:/foo>.\n"
                "    after it is assigned {\n"
                f"        create a dimension point in position<{a_fqun}:/foo>.\n"
                f"        create a dimension point in position<{b_fqun}:/foo>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=main_fqun,
        local_deps={a_fqun: "a", b_fqun: "b"},
        sub_roots={"a": a_fqun, "b": b_fqun},
    )
    assert_no_errors(result)


def test_duplicate_via_full_form_and_short_form_implication():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position<my.domain.com:my_lib:/foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert diags[0].location.column == 34


def test_implication_with_invalid_path_format_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</bad/>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</root>.\n"
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
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38


def test_implication_invalid_name_does_not_become_duplicate():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</bad/>.\n"
        "    it also assigns the position</bad/>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</root>.\n"
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
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38
    assert isinstance(diags[1], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[1].path == "/bad/"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 38


def test_invalid_implication_name_used_in_body_does_not_satisfy_chain_start():
    source = (
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</bad/>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</bad/>.\n"
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
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38
    assert isinstance(diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[1].source_global_name == "position</bad/>"
    assert diags[1].full_global_name == "position<my.domain.com:my_lib:/bad/>"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 37
    assert isinstance(diags[2], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[2].path == "/bad/"
    assert diags[2].location.line == 4
    assert diags[2].location.column == 50


def test_circular_implication_emits_diagnostic(validate_project: ValidateProject):
    result = validate_project(
        {
            "foo.dfn": (
                "define the potential position<my.domain.com:my_lib:/foo> {\n"
                "    it also assigns the position</bar>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</bar>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": (
                "define the potential position<my.domain.com:my_lib:/bar> {\n"
                "    it also assigns the position</foo>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</foo>.\n"
                "    }\n"
                "}\n"
            ),
        },
        entry_file="foo.dfn",
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("foo.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == PurePosixPath("bar.dfn")
    diags = result.file_results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/foo>",
        "position<my.domain.com:my_lib:/bar>",
        "position<my.domain.com:my_lib:/foo>",
    ]
    assert diags[0].location.line == 2
    assert diags[0].location.column == 25


def test_unused_implication_on_global_position_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</root>.\n"
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
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_unused_implication_on_action_error():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    it also assigns the position</foo>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
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
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_implication_used_only_in_constraint_block_is_unused():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</foo>.\n"
        "    }\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</root>.\n"
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
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_implication_used_only_mid_chain_via_self_ref_is_unused():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</foo>.\n"
        "    }\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</root>::position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_two_implication_one_used_one_unused():
    source = (
        "define the potential position<my.domain.com:my_lib:/foo>.\n"
        "define the potential position<my.domain.com:my_lib:/bar>.\n"
        "define the potential position<my.domain.com:my_lib:/root> {\n"
        "    it also assigns the position</foo>.\n"
        "    it also assigns the position</bar>.\n"
        "    after it is assigned {\n"
        "        create a dimension point in position</foo>.\n"
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
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</bar>"
    assert diags[0].location.line == 5
    assert diags[0].location.column == 25


def test_implication_for_nonexistent_quality_used_in_body(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</nonexistent>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</nonexistent>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert len(result.file_results) == 1
    assert result.file_results[0].file_path == PurePosixPath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "nonexistent.dfn"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 34
