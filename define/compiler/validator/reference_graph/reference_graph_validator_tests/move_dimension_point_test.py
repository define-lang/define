# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)


def test_valid_local_positions(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "        the position<from_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    assert results[0].diagnostics == []


def test_duplicate_source_definition_does_not_add_move_constraint_diagnostics(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</dest>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<gateway>::position</dest>.\n"
                "    }\n"
                "}\n"
            ),
            "dest.def": (
                "define the potential position<my.domain.com:my_lib:/dest> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</required>.\n"
                "    }\n"
                "}\n"
            ),
            "required.def": (
                "define the potential action<my.domain.com:my_lib:/required>.\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "action"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 1


def test_undefined_from_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<to_pos>.\n"
        "    it happens when {\n"
        "        the position<to_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<no_such_pos>"
        " to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 46


def test_undefined_to_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    it happens when {\n"
        "        the position<from_pos> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<from_pos>"
        " to position<no_such_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 68


def test_both_positions_undefined(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<bad_from>"
        " to position<bad_to>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<bad_from>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 46
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<bad_to>"
    assert diags[1].location.line == 6
    assert diags[1].location.column == 68


def test_same_fqun_must_use_short_form_in_from(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<to_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<gateway>::position</other>.\n"
                "        move the dimension point in position<gateway>::position<my.domain.com:my_lib:/other> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 65


def test_same_fqun_must_use_short_form_in_to(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<from_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<gateway>::position<my.domain.com:my_lib:/other>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 87


def test_valid_global_to_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos>.\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position</global_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "global_pos.def": "define the potential position<my.domain.com:my_lib:/global_pos>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "position</global_pos>"
    assert all_diags[0].full_global_name == "position<my.domain.com:my_lib:/global_pos>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 60


def test_move_from_a_position_to_itself(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 52
    assert diags[0].position_name == "position<a>"


def test_move_from_a_chained_position_to_itself(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x> to position<a>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 79
    assert all_diags[0].position_name == "position<a>::position</x>"


def test_move_to_same_position_does_not_mark_unknown(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "        move the dimension point in position<a> to position<a>.\n"
        "        create a dimension point in position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 52
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[1].location.line == 9
    assert diags[1].location.column == 37
    assert diags[1].position_name == "position<a>"
    assert diags[1].created_at.line == 7


def test_move_to_chained_prefix_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.def": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 81
    assert all_diags[0].source_position == "position<local_pos>"
    assert all_diags[0].target_position == "position<local_pos>::position</target_pos>"


def test_move_to_chained_prefix_marks_unknown(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "        create a dimension point in position<local_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.def": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 81
    assert all_diags[0].source_position == "position<local_pos>"
    assert all_diags[0].target_position == "position<local_pos>::position</target_pos>"
