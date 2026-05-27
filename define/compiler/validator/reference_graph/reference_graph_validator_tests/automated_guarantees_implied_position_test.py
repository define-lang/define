# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph


def test_create_in_implied_position_emits_occupied_by_new(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 48
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


def test_destroy_in_implied_position_emits_empty(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 66
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"


def test_unknown_state_in_implied_position_propagates_to_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        destroy the particle in position</implied>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # Inner's second destroy on empty /implied raises one
    # DestroyInEmptyPositionDiagnostic and marks /implied unknown.
    # /test's subsequent destroy on box::/implied is suppressed because
    # the unknown state propagated to the caller.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.end_line == 9
    assert all_diags[0].location.end_column == 51
    assert all_diags[0].location.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].position_name == "position</implied>"


def test_move_implied_to_implied_emits_occupied_by_existing(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_b.dfn": "define the potential position<my.domain.com:my_lib:/implied_b>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    it also assigns the position</implied_b>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied_a>.\n"
                "        move the particle in position</implied_a> to position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 65
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_b>"
    assert all_diags[0].populated_at.line == 9
    assert all_diags[0].populated_at.column == 54
    assert all_diags[0].populated_at.end_line == 9
    assert all_diags[0].populated_at.end_column == 74
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


def test_move_implied_to_local_sink_emits_only_empty(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</implied> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 66
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"


def test_move_local_to_implied_emits_occupied_by_new(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_local>.\n"
                "        create a particle in position<_local>.\n"
                "        move the particle in position<_local> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"
    assert all_diags[0].populated_at.line == 9
    assert all_diags[0].populated_at.column == 50
    assert all_diags[0].populated_at.end_line == 9
    assert all_diags[0].populated_at.end_column == 68
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


def test_round_trip_implied_local_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner creates implied, moves to local, returns to implied. Caller sees implied still occupied (round trip preserved the particle)."""
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_local>.\n"
                "        create a particle in position</implied>.\n"
                "        move the particle in position</implied> to position<_local>.\n"
                "        move the particle in position<_local> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 50
    assert all_diags[0].populated_at.end_line == 10
    assert all_diags[0].populated_at.end_column == 68
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


_PARENT_FQUN = "my.domain.com:parent_lib"
_CHILD_FQUN = "my.domain.com:child_lib"


def test_implied_position_guarantee_propagates_across_fqun(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner in child FQUN creates in /implied (in child FQUN). Parent-FQUN test sees position<box>::position<child:/implied> filled."""
    result = validate_project_with_reference_graph(
        {
            "lib/implied.dfn": f"define the potential position<{_CHILD_FQUN}:/implied>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_CHILD_FQUN}:/inner> {{\n"
                f"    it also assigns the position</implied>.\n"
                f"    define the position<trigger_pos>.\n"
                f"    it happens when {{\n"
                f"        the position<trigger_pos> has a particle.\n"
                f"    }} and it does {{\n"
                f"        create a particle in position</implied>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_PARENT_FQUN}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a particle.\n"
                f"    }} and it does {{\n"
                f"        define the position<box> {{\n"
                f"            it may only contain particles where {{\n"
                f"                it has the action<{_CHILD_FQUN}:/inner>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a particle in position<box>.\n"
                f"        create a particle in position<box>::action<{_CHILD_FQUN}:/inner>::position<trigger_pos>.\n"
                f"        create a particle in position<box>::position<{_CHILD_FQUN}:/implied>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_FQUN,
        local_deps={_CHILD_FQUN: "lib"},
        sub_roots={"lib": _CHILD_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 87
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == f"position<box>::position<{_CHILD_FQUN}:/implied>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 48
    assert all_diags[0].populated_at.file_path == PurePosixPath("lib/inner.dfn")


def test_init_block_create_in_transitive_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "transitive_implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/transitive_implied>.\n"
            ),
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</transitive_implied>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</transitive_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</transitive_implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</transitive_implied>"
    assert all_diags[0].populated_at.line == 4
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 4
    assert all_diags[0].populated_at.end_column == 59
    assert all_diags[0].populated_at.file_path == PurePosixPath("implier.dfn")


def test_init_block_move_between_implied_positions(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_b.dfn": "define the potential position<my.domain.com:my_lib:/implied_b>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    it also assigns the position</implied_b>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</implied_a>.\n"
                "        move the particle in position</implied_a> to position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 65
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_b>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 54
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 74
    assert all_diags[0].populated_at.file_path == PurePosixPath("implier.dfn")


def test_caller_pre_filled_implied_untouched_by_callee_remains(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</implied>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 63
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied>"
    assert all_diags[0].populated_at.line == 13
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 13
    assert all_diags[0].populated_at.end_column == 63
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")


def test_swap_two_implied_positions_via_local(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_b.dfn": "define the potential position<my.domain.com:my_lib:/implied_b>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    it also assigns the position</implied_b>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_tmp>.\n"
                "        create a particle in position</implied_a>.\n"
                "        create a particle in position</implied_b>.\n"
                "        move the particle in position</implied_a> to position<_tmp>.\n"
                "        move the particle in position</implied_b> to position</implied_a>.\n"
                "        move the particle in position<_tmp> to position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 65
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_a>"
    assert all_diags[0].populated_at.line == 12
    assert all_diags[0].populated_at.column == 54
    assert all_diags[0].populated_at.end_line == 12
    assert all_diags[0].populated_at.end_column == 74
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 65
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied_b>"
    assert all_diags[1].populated_at.line == 13
    assert all_diags[1].populated_at.column == 48
    assert all_diags[1].populated_at.end_line == 13
    assert all_diags[1].populated_at.end_column == 68
    assert all_diags[1].populated_at.file_path == PurePosixPath("inner.dfn")


def test_cross_fqun_implied_position_init_block(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/a.dfn": (
                f"define the potential position<{_CHILD_FQUN}:/a> {{\n"
                f"    after it is assigned {{\n"
                f"        create a particle in position</a>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/b.dfn": (
                f"define the potential position<{_CHILD_FQUN}:/b> {{\n"
                f"    it may only contain particles where {{\n"
                f"        it has the position</a>.\n"
                f"    }}\n"
                f"    after it is assigned {{\n"
                f"        create a particle in position</b>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_PARENT_FQUN}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a particle.\n"
                f"    }} and it does {{\n"
                f"        define the position<box> {{\n"
                f"            it may only contain particles where {{\n"
                f"                it has the position<{_CHILD_FQUN}:/b>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a particle in position<box>.\n"
                f"        create a particle in position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_FQUN,
        local_deps={_CHILD_FQUN: "lib"},
        sub_roots={"lib": _CHILD_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 119
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>"
    )
    assert all_diags[0].populated_at.line == 3
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 3
    assert all_diags[0].populated_at.end_column == 42
    assert all_diags[0].populated_at.file_path == PurePosixPath("lib/a.dfn")


def test_create_in_implied_action_interface_position_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner creates in an implied action's interface position (action</foo>::position<iface>); /test sees position<box>::action</foo>::position<iface> filled."""
    result = validate_project_with_reference_graph(
        {
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<iface>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the action</foo>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</foo>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</foo>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</foo>::position<iface>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 59
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")
