# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_MAIN_FQUN = "mv:define-lang.org:main_lib"
_DEP_FQUN = "mv:define-lang.org:dep_lib"


def test_cross_fqun_inner_requirement_renders_correctly(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN scenario: the inner action and a position it references are in a different FQUN.

    /inner is in _DEP_FQUN, has position<item> constrained with position</x> (also in
    _DEP_FQUN), and creates in position<item>::position</x>. The propagated requirement's
    position_name should use the source form from /outer's code for the action reference
    (fully-qualified) and the source form from /inner's code for position</x>.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # /test fills position<item> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
    )
    # /test fills position<item>::position</x> which /inner requires empty (propagated)
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[1].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 12,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN OCCUPIED propagation: /inner is in _DEP_FQUN with position</x>.

    /inner moves from position<item>::position</x>, creating an OCCUPIED requirement
    on position<item>::position</x>. This requirement propagates through /outer to
    /test. /test fills it, satisfying the requirement.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN OCCUPIED violation: /inner is in _DEP_FQUN with position</x>.

    /inner moves from position<item>::position</x>, creating OCCUPIED requirements
    on position<item> and position<item>::position</x>. These propagate through
    /outer to /test. /test fills position<item> but not position<item>::position</x>.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                f"        create a particle in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_complex_chain_same_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A deeply-chained trigger path through nested actions in the same FQUN.

    /test triggers /foo through position<local>::position</x>::action</foo>::position<trigger_pos>.
    /foo triggers /middle through position<iface>::action</middle>::position<trigger_pos>.
    /middle triggers /bar through position<mid_iface>::action</bar>::position<trigger_pos>.
    /bar requires position<item> to be empty. The propagated position_name should be:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<mid_iface>::action</bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": (
                "define the potential action<my.domain.com:my_lib:/bar> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::position</x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/foo>"
    assert (
        all_diags[0].position_name
        == "position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/foo>",
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/foo>",
            "triggered_quality_name": _MIDDLE,
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": "action<my.domain.com:my_lib:/bar>",
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/bar>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        ("action<my.domain.com:my_lib:/foo>", _MIDDLE),
        (_TEST, "action<my.domain.com:my_lib:/foo>"),
        (_MIDDLE, "action<my.domain.com:my_lib:/bar>"),
    }


def test_complex_chain_cross_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same structure as the same-FQUN complex chain, but /bar lives in a different FQUN.

    /bar is in dep_lib and has an interface position with a constraint on position</x>,
    requiring position<item>::position</x> to be empty. /middle fills /bar's
    position<item> to satisfy the occupied requirement. The propagated position_name
    should render /bar and its positions with canonical FQUN names:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<dep_fqun:/bar>::position<item>::position<dep_fqun:/x>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                f"define the potential position<{_MAIN_FQUN}:/x> {{\n"
                "    it may only contain particles where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/bar.dfn": (
                f"define the potential action<{_DEP_FQUN}:/bar> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/middle> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain particles where {\n"
                f"            it has the action<{_DEP_FQUN}:/bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                f"        create a particle in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a particle in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/foo> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::position</x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                f"        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a particle in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a particle in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/foo>"
    assert (
        all_diags[0].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>",
            "triggered_quality_name": None,
            "line": 15,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "middle.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is True
    assert all_diags[1].action_name == f"action<{_MAIN_FQUN}:/foo>"
    assert (
        all_diags[1].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "line": 11,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "line": 12,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/foo>"),
        (f"action<{_MAIN_FQUN}:/foo>", f"action<{_MAIN_FQUN}:/middle>"),
        (f"action<{_MAIN_FQUN}:/middle>", f"action<{_DEP_FQUN}:/bar>"),
    }
