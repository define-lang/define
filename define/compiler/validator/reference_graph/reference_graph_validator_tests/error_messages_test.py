# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_action_calls

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"


def test_local_duplicate_dimension_point_format(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a dimension point in position<pos>.\n"
        "        create a dimension point in position<pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 37\n"
        "        create a dimension point in position<pos>.\n"
        "                                    ^\n"
        "a dimension point already exists in 'position<pos>';"
        " it was put there at:\n"
        "line 7, column 37"
    )


def test_move_from_empty_position_format(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 37\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "                                    ^\n"
        "cannot move a dimension point from 'position<from_pos>'"
        " because it does not contain one"
    )


def test_deferred_position_chain_error_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</pos_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "test.dfn": source,
            "pos_b.dfn": (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong.dfn": "define the potential position<my.domain.com:my_lib:/wrong>.\n",
        }
    )
    test_result = next(
        r
        for r in result.program_result.file_results
        if r.file_path == PurePosixPath("test.dfn")
    )
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 10, column 72\n'
        "        create a dimension point in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "                                                                       ^\n"
        "'position<my.domain.com:my_lib:/wrong>' is not declared as one of the"
        " 'it has the' requirements in the definition of"
        " 'position<my.domain.com:my_lib:/pos_b>'"
    )


def test_deferred_action_chain_error_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the action</act_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "test.dfn": source,
            "act_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pos_c>.\n"
                "    it happens when {\n"
                "        the position<pos_c> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    test_result = next(
        r
        for r in result.program_result.file_results
        if r.file_path == PurePosixPath("test.dfn")
    )
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 10, column 70\n'
        "        create a dimension point in position<pos_a>::action</act_b>::position<no_such>.\n"
        "                                                                     ^\n"
        "'position<no_such>' is not defined inside the definition of"
        " 'action<my.domain.com:my_lib:/act_b>'"
    )


def test_action_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<box>.\n"
        "        create a dimension point in position<box>::action</other>::position<item>.\n"
        "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == (
        'File "test.dfn", line 13, column 37\n'
        "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
        "                                    ^\n"
        "this line is triggering `action<my.domain.com:my_lib:/other>` to run.\n"
        "However, 'position<box>::action</other>::position<item>'"
        " must be empty before that action runs, and it is not empty.\n"
        "It was filled at:\n"
        'File "test.dfn", line 12, column 37\n\n'
        "This requirement happens because of:\n"
        'File "other.dfn", line 7, column 37'
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_action_requires_occupied_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<box>.\n"
        "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == (
        'File "test.dfn", line 12, column 37\n'
        "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
        "                                    ^\n"
        "this line is triggering `action<my.domain.com:my_lib:/other>` to run.\n"
        "However, 'position<box>::action</other>::position<item>'"
        " must be occupied before that action runs, and it not occupied.\n\n"
        "This requirement happens because of:\n"
        'File "other.dfn", line 8, column 37'
    )


def test_propagated_action_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "inner.dfn": (
            "define the potential action<my.domain.com:my_lib:/inner> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<item>.\n"
            "    }\n"
            "}\n"
        ),
        "middle.dfn": (
            "define the potential action<my.domain.com:my_lib:/middle> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<mid_iface> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</inner>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
        "outer.dfn": (
            "define the potential action<my.domain.com:my_lib:/outer> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<out_iface> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</middle>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<out_iface>::action</middle>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<box> {\n"
            "            it may only contain dimension points where {\n"
            "                it has the action</outer>.\n"
            "            }\n"
            "        }\n"
            "        create a dimension point in position<box>.\n"
            "        create a dimension point in position<box>::action</outer>::position<out_iface>.\n"
            "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
            "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
            "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == (
        'File "test.dfn", line 15, column 37\n'
        "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
        "                                    ^\n"
        "this line is triggering `action<my.domain.com:my_lib:/inner>` to run.\n"
        "However, 'position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>'"
        " must be empty before that action runs, and it is not empty.\n"
        "It was filled at:\n"
        'File "test.dfn", line 14, column 37\n'
        "\n"
        "This requirement happens because of:\n"
        'File "outer.dfn", line 11, column 37\n'
        '  File "middle.dfn", line 11, column 37\n'
        '    File "inner.dfn", line 7, column 37'
    )
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _MIDDLE, _INNER)


def test_move_violates_constraints_error_message(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the position</x>.\n"
        "                it has the action</y>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<from_pos>.\n"
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "test.dfn": source,
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential action<my.domain.com:my_lib:/y> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 14, column 59\n'
        "        move the dimension point in position<from_pos> to position<to_pos>.\n"
        "                                                          ^\n"
        "cannot move a dimension point\n"
        "  from: position<from_pos>\n"
        "    to: position<to_pos>\n"
        "because the dimension point being moved does not have the required qualities:\n"
        "  position<my.domain.com:my_lib:/x>\n"
        "  action<my.domain.com:my_lib:/y>"
    )


def test_destroy_in_emptied_interface_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<box>.\n"
        "        create a dimension point in position<box>::action</other>::position<item>.\n"
        "        destroy the dimension point in position<box>::action</other>::position<item>.\n"
        "        destroy the dimension point in position<box>::action</other>::position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == (
        'File "test.dfn", line 14, column 40\n'
        "        destroy the dimension point in position<box>::action</other>::position<item>.\n"
        "                                       ^\n"
        "cannot destroy a dimension point in"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one; it was emptied at:\n"
        'File "test.dfn", line 13, column 40'
    )


def test_destroy_in_default_empty_interface_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain dimension points where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a dimension point in position<box>.\n"
        "        destroy the dimension point in position<box>::action</other>::position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == (
        'File "test.dfn", line 12, column 40\n'
        "        destroy the dimension point in position<box>::action</other>::position<item>.\n"
        "                                       ^\n"
        "cannot destroy a dimension point in"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one;"
        " action interface positions are empty by default"
    )
