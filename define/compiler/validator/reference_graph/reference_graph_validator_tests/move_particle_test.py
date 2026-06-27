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
        "        the position<from_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    assert results[0].diagnostics == []


def test_move_from_child_to_parents_empty_sibling(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<parent> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child>.\n"
                "            it has the position</sibling>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<parent>.\n"
                "        create a particle in position<parent>::position</child>.\n"
                "        create a particle in position<parent>::position</child>::position</grandchild>.\n"
                "        move the particle in position<parent>::position</child>::position</grandchild> to position<parent>::position</sibling>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "grandchild.dfn": "define the potential position<my.domain.com:my_lib:/grandchild>.\n",
            "sibling.dfn": "define the potential position<my.domain.com:my_lib:/sibling>.\n",
        }
    )
    assert result.program_result.all_diagnostics == []


def test_duplicate_source_definition_does_not_add_move_constraint_diagnostics(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</dest>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<from_pos> to position<gateway>::position</dest>.\n"
                "    }\n"
                "}\n"
            ),
            "dest.dfn": (
                "define the potential position<my.domain.com:my_lib:/dest> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</required>.\n"
                "    }\n"
                "}\n"
            ),
            "required.dfn": (
                "define the potential action<my.domain.com:my_lib:/required> {\n"
                "    define the position<_noop>.\n"
                "    it happens when {\n"
                "        the position<_noop> has a particle.\n"
                "    } and it does {\n"
                "        define the position<__noop>.\n"
                "        create a particle in position<__noop>.\n"
                "    }\n"
                "}\n"
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
        "        the position<to_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<no_such_pos>"
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
    assert diags[0].location.column == 39


def test_undefined_to_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<from_pos>.\n"
        "    it happens when {\n"
        "        the position<from_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<from_pos>"
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
    assert diags[0].location.column == 61


def test_both_positions_undefined(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<bad_from>"
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
    assert diags[0].location.column == 39
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<bad_to>"
    assert diags[1].location.line == 6
    assert diags[1].location.column == 61


def test_same_fqun_must_use_short_form_in_from(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<to_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        create a particle in position<gateway>::position</other>.\n"
                "        move the particle in position<gateway>::position<my.domain.com:my_lib:/other> to position<to_pos>.\n"
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
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 58


def test_same_fqun_must_use_short_form_in_to(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential position<my.domain.com:my_lib:/other>.\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<from_pos>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>.\n"
                "        move the particle in position<from_pos> to position<gateway>::position<my.domain.com:my_lib:/other>.\n"
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
    assert all_diags[0].location.column == 80


def test_valid_global_to_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos>.\n"
                "    it happens when {\n"
                "        the position<local_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<local_pos> to position</global_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "global_pos.dfn": "define the potential position<my.domain.com:my_lib:/global_pos>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "position</global_pos>"
    assert all_diags[0].full_global_name == "position<my.domain.com:my_lib:/global_pos>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 53


def test_move_to_same_position_does_not_mark_error(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<a>.\n"
        "        create a particle in position<a>.\n"
        "        move the particle in position<a> to position<a>.\n"
        "        create a particle in position<a>.\n"
        "    }\n"
        "}\n"
    )
    results = validate_non_filesystem_with_reference_graph(source).file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 45
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[1].location.line == 9
    assert diags[1].location.column == 30
    assert diags[1].position_name == "position<a>"
    assert diags[1].populated_at.line == 7


def test_move_to_chained_prefix_marks_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<local_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</target_pos>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<local_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<local_pos> to position<local_pos>::position</target_pos>.\n"
                "        create a particle in position<local_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "target_pos.dfn": "define the potential position<my.domain.com:my_lib:/target_pos>.\n",
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 74
    assert all_diags[0].source_position == "position<local_pos>"
    assert all_diags[0].target_position == "position<local_pos>::position</target_pos>"
