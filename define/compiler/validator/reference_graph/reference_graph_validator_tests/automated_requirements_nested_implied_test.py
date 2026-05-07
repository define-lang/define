# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_action_calls

_TEST = "action<my.domain.com:my_lib:/test>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"

_X_DEFINITION = "define the potential position<my.domain.com:my_lib:/x>.\n"

_INNER_DESTROYS_X = (
    "define the potential action<my.domain.com:my_lib:/inner> {\n"
    "    it also assigns the position</x>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a dimension point.\n"
    "    } and it does {\n"
    "        destroy the dimension point in position</x>.\n"
    "    }\n"
    "}\n"
)

_INNER_CREATES_X = (
    "define the potential action<my.domain.com:my_lib:/inner> {\n"
    "    it also assigns the position</x>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in position</x>.\n"
    "    }\n"
    "}\n"
)

_MIDDLE_TRIGGERS_INNER = (
    "define the potential action<my.domain.com:my_lib:/middle> {\n"
    "    it also assigns the action</inner>.\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in action</inner>::position<run>.\n"
    "    }\n"
    "}\n"
)

_TEST_PRE_FILLS_X = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a dimension point.\n"
    "    } and it does {\n"
    "        define the position<box> {\n"
    "            it may only contain dimension points where {\n"
    "                it has the action</middle>.\n"
    "            }\n"
    "        }\n"
    "        create a dimension point in position<box>.\n"
    "        create a dimension point in position<box>::position</x>.\n"
    "        create a dimension point in position<box>::action</middle>::position<run>.\n"
    "    }\n"
    "}\n"
)

_TEST_DOES_NOT_FILL_X = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    define the position<run>.\n"
    "    it happens when {\n"
    "        the position<run> has a dimension point.\n"
    "    } and it does {\n"
    "        define the position<box> {\n"
    "            it may only contain dimension points where {\n"
    "                it has the action</middle>.\n"
    "            }\n"
    "        }\n"
    "        create a dimension point in position<box>.\n"
    "        create a dimension point in position<box>::action</middle>::position<run>.\n"
    "    }\n"
    "}\n"
)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OCCUPIED requirement on /middle's implied position</x> is not yet"
        " inferred from /inner's EmptyGuarantee."
    ),
)
def test_empty_guarantee_creates_occupied_requirement_in_caller_and_test_satisfies(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_DESTROYS_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_PRE_FILLS_X,
        }
    )
    assert result.program_result.all_diagnostics == []
    assert_action_calls(result.action_call_graph, _TEST, _MIDDLE, _INNER)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OCCUPIED requirement on /middle's implied position</x> is not yet"
        " inferred from /inner's EmptyGuarantee."
    ),
)
def test_empty_guarantee_creates_occupied_requirement_in_caller_and_test_violates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_DESTROYS_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_DOES_NOT_FILL_X,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].position_name == "position<box>::position</x>"
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert_action_calls(result.action_call_graph, _TEST, _MIDDLE, _INNER)


def test_occupied_guarantee_creates_empty_requirement_in_caller_and_test_satisfies(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_CREATES_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_DOES_NOT_FILL_X,
        }
    )
    assert result.program_result.all_diagnostics == []
    assert_action_calls(result.action_call_graph, _TEST, _MIDDLE, _INNER)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EMPTY requirement on /middle's implied position</x> is not yet"
        " inferred from /inner's OccupiedByNewGuarantee."
    ),
)
def test_occupied_guarantee_creates_empty_requirement_in_caller_and_test_violates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": _X_DEFINITION,
            "inner.dfn": _INNER_CREATES_X,
            "middle.dfn": _MIDDLE_TRIGGERS_INNER,
            "test.dfn": _TEST_PRE_FILLS_X,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert all_diags[0].position_name == "position<box>::position</x>"
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert all_diags[0].filled_at.line == 12
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _MIDDLE, _INNER)
