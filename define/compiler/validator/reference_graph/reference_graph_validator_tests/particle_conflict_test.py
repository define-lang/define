# pyright: reportUnusedCallResult=false
"""Particle conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateTestdataNonFilesystemWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_constructor_duplicate_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<local>"
    assert diags[0].populated_at.line == 6
    assert diags[0].populated_at.column == 30
    assert diags[0].populated_at.end_line == 6
    assert diags[0].populated_at.end_column == 45
    assert diags[0].populated_at.file_path is None
    assert diags[0].location.line == 7
    assert diags[0].location.column == 30
    assert diags[0].location.end_line == 7
    assert diags[0].location.end_column == 45
    assert diags[0].location.file_path is None


def test_duplicate_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<my_pos>"
    assert diags[0].populated_at.line == 7
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30


def test_different_local_positions(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<pos_a>.\n"
        "        define the position<pos_b>.\n"
        "        create a particle in position<pos_a>.\n"
        "        create a particle in position<pos_b>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_undefined_position_not_tracked_for_duplicates(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<no_such_pos>.\n"
        "        create a particle in position<no_such_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 30
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<no_such_pos>"
    assert diags[1].location.line == 7
    assert diags[1].location.column == 30


def test_two_actions_same_local_position_create_no_error(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a particle in position<my_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a particle in position<my_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_two_actions_same_name_one_duplicate_one_clean(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a particle in position<my_pos>.\n"
        "        create a particle in position<my_pos>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<my_pos>.\n"
        "        create a particle in position<my_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<my_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30


def test_three_actions_particle_isolation(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/act_one> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a particle in position<shared_name>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_two> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a particle in position<shared_name>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act_three> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<shared_name>.\n"
        "        create a particle in position<shared_name>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_definition_block_position_enforced(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<outer_pos>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<outer_pos>.\n"
        "        create a particle in position<outer_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<outer_pos>"
    assert diags[0].populated_at.line == 7
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30
