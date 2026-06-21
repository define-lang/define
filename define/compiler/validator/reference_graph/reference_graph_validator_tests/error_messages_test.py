# pyright: reportUnusedCallResult=false

# TODO: Convert all the other format-snapshot assertions in this file (and in
# the parser_tests and program_validator_tests error_messages_test.py files)
# to use textwrap.dedent triple-quoted strings, matching the pattern of the
# destructor-format tests below.

# TODO: The destruction-related error-message tests (destructor requirements,
# destructor guarantees, auto-destruction, and Destruction Contracts) have grown
# large enough that they really need their own test file, split out from the
# general reference-graph error messages here.

import textwrap

from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.data_structures import define_path
from define.compiler.validator.test_helpers import assert_action_calls

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"


def test_local_duplicate_particle_format(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<pos>.\n"
        "        create a particle in position<pos>.\n"
        "        create a particle in position<pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 30\n"
        "        create a particle in position<pos>.\n"
        "                             ^\n"
        "a particle already exists in 'position<pos>';"
        " it was put there at:\n"
        "line 7, column 30"
    )


def test_move_from_empty_position_format(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos>.\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        "line 8, column 30\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "                             ^\n"
        "cannot move a particle from 'position<from_pos>'"
        " because it does not contain one"
    )


def test_deferred_position_chain_error_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</pos_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "test.dfn": source,
            "pos_b.dfn": (
                "define the potential position<my.domain.com:my_lib:/pos_b> {\n"
                "    it may only contain particles where {\n"
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
        if r.file_path == define_path.DefinePath("test.dfn")
    )
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 10, column 65\n'
        "        create a particle in position<pos_a>::position</pos_b>::position</wrong>.\n"
        "                                                                ^\n"
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
        "        it may only contain particles where {\n"
        "            it has the action</act_b>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<pos_a>::action</act_b>::position<no_such>.\n"
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
                "        the position<pos_c> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    test_result = next(
        r
        for r in result.program_result.file_results
        if r.file_path == define_path.DefinePath("test.dfn")
    )
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 10, column 63\n'
        "        create a particle in position<pos_a>::action</act_b>::position<no_such>.\n"
        "                                                              ^\n"
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
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<item>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 13, column 30
                create a particle in position<box>::action</other>::position<trigger_pos>.
                                     ^
        this line is triggering 'action<my.domain.com:my_lib:/other>' to run.
        However, 'position<box>::action</other>::position<item>' must be empty before that action runs, and it is not empty.
        It was filled at:
        File "test.dfn", line 12, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/other>' inferred this requirement:
            File "other.dfn", line 7, column 30""")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_action_requires_occupied_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 12, column 30
                create a particle in position<box>::action</other>::position<trigger_pos>.
                                     ^
        this line is triggering 'action<my.domain.com:my_lib:/other>' to run.
        However, 'position<box>::action</other>::position<item>' must be occupied before that action runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/other>' inferred this requirement:
            File "other.dfn", line 8, column 30""")


def test_propagated_action_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "inner.dfn": (
            "define the potential action<my.domain.com:my_lib:/inner> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "    }\n"
            "}\n"
        ),
        "middle.dfn": (
            "define the potential action<my.domain.com:my_lib:/middle> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<mid_iface> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</inner>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
        "outer.dfn": (
            "define the potential action<my.domain.com:my_lib:/outer> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<out_iface> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</middle>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
            "                it has the action</outer>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
            "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 15, column 30
                create a particle in position<box>::action</outer>::position<trigger_pos>.
                                     ^
        this line is triggering 'action<my.domain.com:my_lib:/outer>' to run.
        However, 'position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>' must be empty before that action runs, and it is not empty.
        It was filled at:
        File "test.dfn", line 14, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/outer>' triggers 'action<my.domain.com:my_lib:/middle>':
            File "outer.dfn", line 11, column 30
          'action<my.domain.com:my_lib:/middle>' triggers 'action<my.domain.com:my_lib:/inner>':
            File "middle.dfn", line 11, column 30
          'action<my.domain.com:my_lib:/inner>' inferred this requirement:
            File "inner.dfn", line 7, column 30""")
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _MIDDLE, _INNER)


def test_move_violates_constraints_error_message(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<from_pos>.\n"
        "        define the position<to_pos> {\n"
        "            it may only contain particles where {\n"
        "                it has the position</x>.\n"
        "                it has the action</y>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<from_pos>.\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
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
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(source.splitlines())
    assert formatted == (
        'File "test.dfn", line 14, column 52\n'
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "                                                   ^\n"
        "cannot move a particle\n"
        "  from: position<from_pos>\n"
        "    to: position<to_pos>\n"
        "because the particle being moved does not have the required qualities:\n"
        "  position<my.domain.com:my_lib:/x>\n"
        "  action<my.domain.com:my_lib:/y>"
    )


def test_position_init_block_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the position</p>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 11, column 30
                create a particle in position<box>.
                                     ^
        this line creates a particle in 'position<box>'. Doing so assigns 'position<my.domain.com:my_lib:/p>' to that particle, running its Position Initialization Block.
        However, 'position<box>::position</q>' must be empty before that block runs, and it is not empty.
        It was filled at:
        File "q.dfn", line 3, column 30

        This requirement happens because:
          'position<my.domain.com:my_lib:/p>' inferred this requirement:
            File "p.dfn", line 4, column 30""")


def test_position_init_block_requires_occupied_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the position</p>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(test_source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 11, column 30
                create a particle in position<box>.
                                     ^
        this line creates a particle in 'position<box>'. Doing so assigns 'position<my.domain.com:my_lib:/p>' to that particle, running its Position Initialization Block.
        However, 'position<box>::position</q>' must be occupied before that block runs, and it is not occupied.

        This requirement happens because:
          'position<my.domain.com:my_lib:/p>' inferred this requirement:
            File "p.dfn", line 4, column 33""")


def test_destroy_in_emptied_interface_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<item>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
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
        'File "test.dfn", line 14, column 33\n'
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "                                ^\n"
        "cannot destroy a particle in"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one; it was emptied at:\n"
        'File "test.dfn", line 13, column 33'
    )


def test_destroy_in_default_empty_interface_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<box> {\n"
        "            it may only contain particles where {\n"
        "                it has the action</other>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<box>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
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
        'File "test.dfn", line 12, column 33\n'
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "                                ^\n"
        "cannot destroy a particle in"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one;"
        " action interface positions are empty by default"
    )


def test_destructor_requires_occupied_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "child_q.dfn": (
            "define the potential position<my.domain.com:my_lib:/child_q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor>.\n"
            "    }\n"
            "}\n"
        ),
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
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        define the position<staging> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<staging>.\n"
            "        create a particle in position<staging>::position</child_q>.\n"
            "        move the particle in position<staging> to position<box>.\n"
            "        destroy the particle in position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 19, column 33
                destroy the particle in position<box>.
                                        ^
        Destroying the particle in 'position<box>::position</child_q>' triggers the destructor 'action<my.domain.com:my_lib:/destructor>'.

        The particle in 'position<box>::position</child_q>' was originally created at:
        File "test.dfn", line 17, column 30

        However, 'position<box>::position</child_q>::action</destructor>::position<item>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/destructor>' inferred this requirement:
            File "destructor.dfn", line 7, column 30""")


def test_destructor_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "child_q.dfn": (
            "define the potential position<my.domain.com:my_lib:/child_q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor_empty>.\n"
            "    }\n"
            "}\n"
        ),
        "destructor_empty.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
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
            "        define the position<staging> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<staging>.\n"
            "        create a particle in position<staging>::position</child_q>.\n"
            "        move the particle in position<staging> to position<box>.\n"
            "        create a particle in position<box>::position</child_q>::action</destructor_empty>::position<item>.\n"
            "        destroy the particle in position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 20, column 33
                destroy the particle in position<box>.
                                        ^
        Destroying the particle in 'position<box>::position</child_q>' triggers the destructor 'action<my.domain.com:my_lib:/destructor_empty>'.

        The particle in 'position<box>::position</child_q>' was originally created at:
        File "test.dfn", line 17, column 30

        However, 'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before that destructor runs, and it is not empty.
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' was filled at:
        File "test.dfn", line 19, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/destructor_empty>' inferred this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


def test_aware_destructor_requirement_surfaces_as_action_requires_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the destroying action itself knows the destructor (its target constraint declares it), an unmet destructor requirement surfaces as an ActionRequires through normal trigger propagation, whose explanation names the destruction-cascade step rather than reading as a Destruction Contract violation."""
    files = {
        "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
        "destructor.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor> {\n"
            "    it also assigns the position</file>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_holder>.\n"
            "        move the particle in position</file> to position<_holder>.\n"
            "        move the particle in position<_holder> to position</file>.\n"
            "    }\n"
            "}\n"
        ),
        "close_file.dfn": (
            "define the potential action<my.domain.com:my_lib:/close_file> {\n"
            "    define the position<target> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</destructor>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<target>.\n"
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
            "                it has the action</close_file>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<box>::action</close_file>::position<target>.\n"
            "        create a particle in position<box>::action</close_file>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 13, column 30
                create a particle in position<box>::action</close_file>::position<run>.
                                     ^
        this line is triggering 'action<my.domain.com:my_lib:/close_file>' to run.
        However, 'position<box>::action</close_file>::position<target>::position</file>' must be occupied before that action runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor>':
            File "close_file.dfn", line 11, column 33
          'action<my.domain.com:my_lib:/destructor>' inferred this requirement:
            File "destructor.dfn", line 7, column 30""")


def test_destructor_moved_guarantee_names_contracted_origin_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<incoming> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</child>.\n"
        "        }\n"
        "    }\n"
        "    define the position<dest>.\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<tmp> {\n"
        "            it may only contain particles where {\n"
        "                it has the position</child>.\n"
        "            }\n"
        "        }\n"
        "        move the particle in position<incoming> to position<tmp>.\n"
        "        move the particle in position<tmp>::position</child> to position<dest>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph(
        {
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child>.\n"
            ),
            "test.dfn": test_source,
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert all_diags[0].format(test_source.splitlines()) == (
        'File "test.dfn", line 16, column 30\n'
        "        move the particle in position<incoming> to position<tmp>.\n"
        "                             ^\n"
        "a destructor must leave every position in the state it was in when it started.\n"
        "However, this line empties 'position<incoming>' and then nothing puts the same"
        " particle back into that position."
    )
    assert all_diags[1].format(test_source.splitlines()) == (
        'File "test.dfn", line 17, column 65\n'
        "        move the particle in position<tmp>::position</child> to position<dest>.\n"
        "                                                                ^\n"
        "a destructor must leave every position in the state it was in when it started.\n"
        "However, this line moves a particle from"
        " 'position<incoming>::position</child>' into 'position<dest>' and then nothing"
        " moves it back out of that position."
    )


def test_destructor_occupied_guarantee_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    test_source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<item>.\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        create a particle in position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project_with_reference_graph({"test.dfn": test_source})
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert all_diags[0].format(test_source.splitlines()) == (
        'File "test.dfn", line 6, column 30\n'
        "        create a particle in position<item>.\n"
        "                             ^\n"
        "a destructor must leave every position in the state it was in when it started.\n"
        "However, this line creates a new particle in 'position<item>' and then"
        " nothing removes it from that position."
    )


def test_auto_destruction_destructor_requires_empty_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "child_q.dfn": (
            "define the potential position<my.domain.com:my_lib:/child_q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor_empty>.\n"
            "    }\n"
            "}\n"
        ),
        "destructor_empty.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
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
            "        define the position<staging> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<staging>.\n"
            "        create a particle in position<staging>::position</child_q>.\n"
            "        move the particle in position<staging> to position<box>.\n"
            "        create a particle in position<box>::position</child_q>::action</destructor_empty>::position<item>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 18, column 51
                move the particle in position<staging> to position<box>.
                                                          ^
        The particle in 'position<box>' is being automatically destroyed at the end of 'action<my.domain.com:my_lib:/test>'.
        This causes the particle in 'position<box>::position</child_q>' to be destroyed first.
        The above line shows how the particle in 'position<box>::position</child_q>' got into its current position.

        The particle in 'position<box>::position</child_q>' was originally created at:
        File "test.dfn", line 17, column 30

        Destroying 'position<box>::position</child_q>' triggers the destructor 'action<my.domain.com:my_lib:/destructor_empty>'.
        However, 'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before that destructor runs, and it is not empty.
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' was filled at:
        File "test.dfn", line 19, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/destructor_empty>' inferred this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


def test_auto_destruction_destructor_requires_occupied_position_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "child_q.dfn": (
            "define the potential position<my.domain.com:my_lib:/child_q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor>.\n"
            "    }\n"
            "}\n"
        ),
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
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        define the position<staging> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<staging>.\n"
            "        create a particle in position<staging>::position</child_q>.\n"
            "        move the particle in position<staging> to position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 18, column 51
                move the particle in position<staging> to position<box>.
                                                          ^
        The particle in 'position<box>' is being automatically destroyed at the end of 'action<my.domain.com:my_lib:/test>'.
        This causes the particle in 'position<box>::position</child_q>' to be destroyed first.
        The above line shows how the particle in 'position<box>::position</child_q>' got into its current position.

        The particle in 'position<box>::position</child_q>' was originally created at:
        File "test.dfn", line 17, column 30

        Destroying 'position<box>::position</child_q>' triggers the destructor 'action<my.domain.com:my_lib:/destructor>'.
        However, 'position<box>::position</child_q>::action</destructor>::position<item>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/destructor>' inferred this requirement:
            File "destructor.dfn", line 7, column 30""")


def test_auto_destruction_in_position_init_block_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "child_q.dfn": (
            "define the potential position<my.domain.com:my_lib:/child_q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor_empty>.\n"
            "    }\n"
            "}\n"
        ),
        "destructor_empty.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
            "    }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    after it is assigned {\n"
            "        define the position<box> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        define the position<staging> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<staging>.\n"
            "        create a particle in position<staging>::position</child_q>.\n"
            "        move the particle in position<staging> to position<box>.\n"
            "        create a particle in position<box>::position</child_q>::action</destructor_empty>::position<item>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 15, column 51
                move the particle in position<staging> to position<box>.
                                                          ^
        The particle in 'position<box>' is being automatically destroyed at the end of 'position<my.domain.com:my_lib:/test>'.
        This causes the particle in 'position<box>::position</child_q>' to be destroyed first.
        The above line shows how the particle in 'position<box>::position</child_q>' got into its current position.

        The particle in 'position<box>::position</child_q>' was originally created at:
        File "test.dfn", line 14, column 30

        Destroying 'position<box>::position</child_q>' triggers the destructor 'action<my.domain.com:my_lib:/destructor_empty>'.
        However, 'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before that destructor runs, and it is not empty.
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' was filled at:
        File "test.dfn", line 16, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/destructor_empty>' inferred this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


def test_destructor_cascade_through_action_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "destructor_empty.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
            "    }\n"
            "}\n"
        ),
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
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 14, column 30
                create a particle in position<box>::action</inner>::position<run>.
                                     ^
        this line is triggering 'action<my.domain.com:my_lib:/inner>' to run.
        However, 'position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>' must be empty before that action runs, and it is not empty.
        It was filled at:
        File "test.dfn", line 13, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/inner>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "inner.dfn", line 11, column 9
          'action<my.domain.com:my_lib:/destructor_empty>' inferred this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


def test_destructor_cascade_through_position_init_block_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "destructor_empty.dfn": (
            "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
            "    define the position<item>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position<item>.\n"
            "        destroy the particle in position<item>.\n"
            "    }\n"
            "}\n"
        ),
        "q.dfn": (
            "define the potential position<my.domain.com:my_lib:/q> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</destructor_empty>.\n"
            "    }\n"
            "    after it is assigned {\n"
            "        create a particle in position</q>.\n"
            "        create a particle in position</q>::action</destructor_empty>::position<item>.\n"
            "    }\n"
            "}\n"
        ),
        "p.dfn": (
            "define the potential position<my.domain.com:my_lib:/p> {\n"
            "    it also assigns the position</q>.\n"
            "    after it is assigned {\n"
            "        destroy the particle in position</q>.\n"
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
            "                it has the position</p>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 11, column 30
                create a particle in position<box>.
                                     ^
        this line creates a particle in 'position<box>'. Doing so assigns 'position<my.domain.com:my_lib:/p>' to that particle, running its Position Initialization Block.
        However, 'position<box>::position</q>::action</destructor_empty>::position<item>' must be empty before that block runs, and it is not empty.
        It was filled at:
        File "q.dfn", line 7, column 30

        This requirement happens because:
          'position<my.domain.com:my_lib:/p>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "p.dfn", line 4, column 33
          'action<my.domain.com:my_lib:/destructor_empty>' inferred this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


# --- Destruction Contract stacks (DLP 41) ---
#
# These cover the new error stacks where the destroying action could NOT see a
# caller-attached destructor and recorded a Destruction Contract that the
# triggering action verifies. The chain gains a DESTRUCTOR_ATTACHED step (the
# attacher) after the DESTRUCTOR_CASCADE step (the destroyer): destruction comes
# before attachment, as a causal stack.


# TODO: This message points at the trigger position and then talks about a
# destruction, which is confusing. An inferred-requirement message should simply
# state that the position must be occupied (or empty) before the action runs and
# then show the stack, which explains the rest. That likely wants a single
# inferred-requirement diagnostic shared by the Action / Position Init Block /
# Destructor cases; deferred to a future change, so this snapshot pins the
# current (confusing) wording until then.
def test_destruction_contract_requires_occupied_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
        "delete_file_destructor.dfn": (
            "define the potential action<my.domain.com:my_lib:/delete_file_destructor> {\n"
            "    it also assigns the position</file>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_holder>.\n"
            "        move the particle in position</file> to position<_holder>.\n"
            "        move the particle in position<_holder> to position</file>.\n"
            "    }\n"
            "}\n"
        ),
        "close_file.dfn": (
            "define the potential action<my.domain.com:my_lib:/close_file> {\n"
            "    define the position<target> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</file>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<target>.\n"
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
            "                it has the action</close_file>.\n"
            "            }\n"
            "        }\n"
            "        define the position<my_file> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</file>.\n"
            "                it has the action</delete_file_destructor>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<my_file>.\n"
            "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
            "        create a particle in position<box>::action</close_file>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 20, column 30
                create a particle in position<box>::action</close_file>::position<run>.
                                     ^
        Destroying the particle in 'position<box>::action</close_file>::position<target>' triggers the destructor 'action<my.domain.com:my_lib:/delete_file_destructor>'.

        The particle in 'position<box>::action</close_file>::position<target>' was originally created at:
        File "test.dfn", line 18, column 30

        However, 'position<box>::action</close_file>::position<target>::position</file>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_file_destructor>':
            File "close_file.dfn", line 11, column 33
          the destructor 'action<my.domain.com:my_lib:/delete_file_destructor>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 14, column 28
          'action<my.domain.com:my_lib:/delete_file_destructor>' inferred this requirement:
            File "delete_file_destructor.dfn", line 7, column 30""")


def test_destruction_contract_requires_empty_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A caller-attached destructor requires its implied position</p2> empty; a blind filler (which knows only position</p2>) fills it, so /test verifies the empty-requirement violation with the fill site carried up from the contract."""
    files = {
        "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
        "d.dfn": (
            "define the potential action<my.domain.com:my_lib:/d> {\n"
            "    it also assigns the position</p2>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        create a particle in position</p2>.\n"
            "        destroy the particle in position</p2>.\n"
            "    }\n"
            "}\n"
        ),
        "close_file.dfn": (
            "define the potential action<my.domain.com:my_lib:/close_file> {\n"
            "    define the position<target>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<target>.\n"
            "    }\n"
            "}\n"
        ),
        "filler.dfn": (
            "define the potential action<my.domain.com:my_lib:/filler> {\n"
            "    define the position<incoming> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</p2>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<box> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</close_file>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<incoming>::position</p2>.\n"
            "        move the particle in position<incoming> to position<box>::action</close_file>::position<target>.\n"
            "        create a particle in position<box>::action</close_file>::position<run>.\n"
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
            "                it has the action</filler>.\n"
            "            }\n"
            "        }\n"
            "        define the position<my_file> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</d>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<my_file>.\n"
            "        move the particle in position<my_file> to position<box>::action</filler>::position<incoming>.\n"
            "        create a particle in position<box>::action</filler>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 19, column 30
                create a particle in position<box>::action</filler>::position<run>.
                                     ^
        Destroying the particle in 'position<box>::action</filler>::position<incoming>' triggers the destructor 'action<my.domain.com:my_lib:/d>'.

        The particle in 'position<box>::action</filler>::position<incoming>' was originally created at:
        File "test.dfn", line 17, column 30

        However, 'position<box>::action</filler>::position<incoming>::position</p2>' must be empty before that destructor runs, and it is not empty.
        'position<box>::action</filler>::position<incoming>::position</p2>' was filled at:
        File "filler.dfn", line 17, column 30

        This requirement happens because:
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/d>':
            File "close_file.dfn", line 7, column 33
          the destructor 'action<my.domain.com:my_lib:/d>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 13, column 28
          'action<my.domain.com:my_lib:/d>' inferred this requirement:
            File "d.dfn", line 6, column 30""")


# TODO: This points at the move line but names 'position<local_box>', which does
# not appear in the pointed-at line (it is a local position inside mid). A future
# change should show the stack of positional moves that carried the particle to
# where it was auto-destroyed, instead of naming a position out of context. This
# snapshot pins the current (confusing) wording until then.
def test_destruction_contract_auto_destruction_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
        "delete_destructor.dfn": (
            "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
            "    it also assigns the position</file>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_holder>.\n"
            "        move the particle in position</file> to position<_holder>.\n"
            "        move the particle in position<_holder> to position</file>.\n"
            "    }\n"
            "}\n"
        ),
        "mid.dfn": (
            "define the potential action<my.domain.com:my_lib:/mid> {\n"
            "    define the position<incoming> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</file>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<local_box>.\n"
            "        move the particle in position<incoming> to position<local_box>.\n"
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
            "                it has the action</mid>.\n"
            "            }\n"
            "        }\n"
            "        define the position<my_file> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</file>.\n"
            "                it has the action</delete_destructor>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<my_file>.\n"
            "        move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.\n"
            "        create a particle in position<box>::action</mid>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 19, column 51
                move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.
                                                          ^
        The particle in 'position<local_box>' is being automatically destroyed at the end of 'action<my.domain.com:my_lib:/mid>'.
        This causes the particle in 'position<box>::action</mid>::position<incoming>' to be destroyed first.
        The above line shows how the particle in 'position<box>::action</mid>::position<incoming>' got into its current position.

        The particle in 'position<box>::action</mid>::position<incoming>' was originally created at:
        File "test.dfn", line 18, column 30

        Destroying 'position<box>::action</mid>::position<incoming>' triggers the destructor 'action<my.domain.com:my_lib:/delete_destructor>'.
        However, 'position<box>::action</mid>::position<incoming>::position</file>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/mid>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_destructor>':
            File "mid.dfn", line 11, column 9
          the destructor 'action<my.domain.com:my_lib:/delete_destructor>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 14, column 28
          'action<my.domain.com:my_lib:/delete_destructor>' inferred this requirement:
            File "delete_destructor.dfn", line 7, column 30""")


def test_destruction_contract_init_block_attacher_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
        "delete_destructor.dfn": (
            "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
            "    it also assigns the position</file>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_holder>.\n"
            "        move the particle in position</file> to position<_holder>.\n"
            "        move the particle in position<_holder> to position</file>.\n"
            "    }\n"
            "}\n"
        ),
        "carrier.dfn": (
            "define the potential position<my.domain.com:my_lib:/carrier> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</file>.\n"
            "        it has the action</delete_destructor>.\n"
            "    }\n"
            "}\n"
        ),
        "close_file.dfn": (
            "define the potential action<my.domain.com:my_lib:/close_file> {\n"
            "    define the position<target> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</file>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<target>.\n"
            "    }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</carrier>.\n"
            "    after it is assigned {\n"
            "        define the position<box> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</close_file>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position</carrier>.\n"
            "        move the particle in position</carrier> to position<box>::action</close_file>::position<target>.\n"
            "        create a particle in position<box>::action</close_file>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 12, column 30
                create a particle in position<box>::action</close_file>::position<run>.
                                     ^
        Destroying the particle in 'position<box>::action</close_file>::position<target>' triggers the destructor 'action<my.domain.com:my_lib:/delete_destructor>'.

        The particle in 'position<box>::action</close_file>::position<target>' was originally created at:
        File "test.dfn", line 10, column 30

        However, 'position<box>::action</close_file>::position<target>::position</file>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_destructor>':
            File "close_file.dfn", line 11, column 33
          the destructor 'action<my.domain.com:my_lib:/delete_destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/carrier>':
            File "carrier.dfn", line 4, column 20
          'action<my.domain.com:my_lib:/delete_destructor>' inferred this requirement:
            File "delete_destructor.dfn", line 7, column 30""")


def test_destruction_contract_cascade_child_format(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    files = {
        "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
        "child_destructor.dfn": (
            "define the potential action<my.domain.com:my_lib:/child_destructor> {\n"
            "    it also assigns the position</file>.\n"
            "    it happens when {\n"
            "        this particle is being destroyed.\n"
            "    } and it does {\n"
            "        define the position<_holder>.\n"
            "        move the particle in position</file> to position<_holder>.\n"
            "        move the particle in position<_holder> to position</file>.\n"
            "    }\n"
            "}\n"
        ),
        "child.dfn": (
            "define the potential position<my.domain.com:my_lib:/child> {\n"
            "    it may only contain particles where {\n"
            "        it has the action</child_destructor>.\n"
            "    }\n"
            "}\n"
        ),
        "close_file.dfn": (
            "define the potential action<my.domain.com:my_lib:/close_file> {\n"
            "    define the position<target>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<target>.\n"
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
            "                it has the action</close_file>.\n"
            "            }\n"
            "        }\n"
            "        define the position<my_file> {\n"
            "            it may only contain particles where {\n"
            "                it has the position</child>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<my_file>.\n"
            "        create a particle in position<my_file>::position</child>.\n"
            "        move the particle in position<my_file> to position<box>::action</close_file>::position<target>.\n"
            "        create a particle in position<box>::action</close_file>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project_with_reference_graph(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 20, column 30
                create a particle in position<box>::action</close_file>::position<run>.
                                     ^
        Destroying the particle in 'position<box>::action</close_file>::position<target>::position</child>' triggers the destructor 'action<my.domain.com:my_lib:/child_destructor>'.

        The particle in 'position<box>::action</close_file>::position<target>::position</child>' was originally created at:
        File "test.dfn", line 18, column 30

        However, 'position<box>::action</close_file>::position<target>::position</child>::position</file>' must be occupied before that destructor runs, and it is not occupied.

        This requirement happens because:
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/child_destructor>':
            File "close_file.dfn", line 7, column 33
          the destructor 'action<my.domain.com:my_lib:/child_destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child>':
            File "child.dfn", line 3, column 20
          'action<my.domain.com:my_lib:/child_destructor>' inferred this requirement:
            File "child_destructor.dfn", line 7, column 30""")
