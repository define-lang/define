# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_CHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/child_destructor>"

# Creates and destroys a particle in its own interface position, so it
# requires that position to be empty when the destructor fires.
_DESTRUCTOR_REQUIRES_EMPTY = (
    "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "        destroy the particle in position<item>.\n"
    "    }\n"
    "}\n"
)


def _named_destructor_noop(name: str) -> str:
    return (
        f"define the potential action<my.domain.com:my_lib:/{name}> {{\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )


def test_local_position_left_occupied_fires_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_local_position_in_constructor_left_occupied_fires_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_in_reverse_definition_order(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Two local positions occupied at end of block fire destructors in reverse definition order."""
    result = validate_project_with_reference_graph(
        {
            "destructor_a.dfn": _named_destructor_noop("destructor_a"),
            "destructor_b.dfn": _named_destructor_noop("destructor_b"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box_a> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box_a>.\n"
                "        create a particle in position<box_b>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    edges = result.action_call_graph.edges()
    # box_b was defined later, so destructor_b fires first; destructor_a after.
    assert edges == [(_TEST, _DESTRUCTOR_B), (_TEST, _DESTRUCTOR_A)]


def test_empty_local_position_does_not_fire_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A local position defined but never filled fires no destructor at block end."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        define the position<other>.\n"
                "        create a particle in position<other>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 29
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.edges() == []


def test_explicit_destroy_before_block_end_does_not_double_fire(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An explicit destroy empties the position; auto-destruction doesn't re-fire."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    edges = result.action_call_graph.edges()
    assert edges == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_cascades_into_child_particle_destructors(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A local position with a child particle fires the child's destructor through cascade."""
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _CHILD_DESTRUCTOR)]


def test_move_from_interface_position_to_local_then_auto_destroy(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A caller-passed particle moved from an interface position into a local fires its destructor at end of block."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        move the particle in position<incoming> to position<local>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_move_from_implied_position_to_local_then_auto_destroy(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A caller-passed particle moved from an implied position into a local fires its destructor at end of block."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "implied_q.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied_q> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied_q>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        move the particle in position</implied_q> to position<local>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_auto_destruction_failing_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name == "position<box>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_auto_destruction_failing_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            # Moves item to a holder and back, requiring item to be occupied
            # when the destructor fires.
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position<item> to position<_holder>.\n"
                "        move the particle in position<_holder> to position<item>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR
    assert diag.required_empty is False
    assert diag.position_name == "position<box>::action</destructor>::position<item>"
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )


def test_constructor_auto_destruction_failing_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 10
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name == "position<box>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 7,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 10,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_auto_destruction_failing_in_reverse_definition_order(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box_a> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box_a>.\n"
                "        create a particle in position<box_a>::action</destructor_empty>::position<item>.\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # Diagnostics are sorted by source location, so box_a (line 16) precedes
    # box_b (line 18) even though box_b is destroyed first.
    box_a_diag = all_diags[0]
    assert isinstance(box_a_diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert box_a_diag.location.line == 16
    assert box_a_diag.location.column == 30
    assert box_a_diag.location.file_path == PurePosixPath("test.dfn")
    assert box_a_diag.action_name == _DESTRUCTOR_EMPTY
    assert box_a_diag.required_empty is True
    assert (
        box_a_diag.position_name
        == "position<box_a>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        box_a_diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box_a>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box_a>",
            "triggered_quality_name": _TEST,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )

    box_b_diag = all_diags[1]
    assert isinstance(box_b_diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert box_b_diag.location.line == 18
    assert box_b_diag.location.column == 30
    assert box_b_diag.location.file_path == PurePosixPath("test.dfn")
    assert box_b_diag.action_name == _DESTRUCTOR_EMPTY
    assert box_b_diag.required_empty is True
    assert (
        box_b_diag.position_name
        == "position<box_b>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        box_b_diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 13,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box_b>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box_b>",
            "triggered_quality_name": _TEST,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_cascade_child_auto_destruction_failing_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "child_q.dfn": (
                "define the potential position<my.domain.com:my_lib:/child_q> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</destructor_empty>.\n"
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
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child_q>.\n"
                "        create a particle in position<box>::position</child_q>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 11
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert diag.position_name == (
        "position<box>::position</child_q>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/child_q>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 3,
            "column": 20,
            "file_path": "child_q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::position</child_q>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</child_q>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": _TEST,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_interface_to_local_auto_destruction_failing_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor_empty>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<incoming> to position<local>.\n"
                "        create a particle in position<local>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 16
    assert diag.location.column == 52
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name
        == "position<local>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 4,
            "column": 24,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": _TEST,
            "line": 16,
            "column": 52,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 16,
            "column": 52,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_implied_to_local_auto_destruction_failing_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "implied_q.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied_q> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</destructor_empty>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied_q>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position</implied_q> to position<local>.\n"
                "        create a particle in position<local>::action</destructor_empty>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 12
    assert diag.location.column == 54
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _DESTRUCTOR_EMPTY
    assert diag.required_empty is True
    assert (
        diag.position_name
        == "position<local>::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/implied_q>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 3,
            "column": 20,
            "file_path": "implied_q.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.AUTO_DESTRUCTION,
            "enclosing_quality_name": "position<local>",
            "triggered_quality_name": _TEST,
            "line": 12,
            "column": 54,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 12,
            "column": 54,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )


def test_destructor_requirement_propagates_to_caller_via_interface(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A destructor's requirement on a caller-passed particle propagates to its caller's caller."""
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor_empty>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<incoming> to position<local>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<entry>.\n"
                "    it happens when {\n"
                "        the position<entry> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<incoming>.\n"
                "        create a particle in position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>.\n"
                "        create a particle in position<box>::action</inner>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 14
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.action_name == _INNER
    assert diag.required_empty is True
    assert diag.position_name == (
        "position<box>::action</inner>::position<incoming>"
        "::action</destructor_empty>::position<item>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _INNER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<incoming>",
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 4,
            "column": 24,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _DESTRUCTOR_EMPTY,
            "line": 11,
            "column": 9,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )
