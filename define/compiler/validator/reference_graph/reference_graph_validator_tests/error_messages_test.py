# pyright: reportUnusedCallResult=false

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from define.compiler.data_structures import define_path
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateProject

# Keep Define source inline in this module because these tests compare rendered
# diagnostics against the exact source lines supplied to the formatter.

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"

# Keep Define source inline in this module so each formatted diagnostic can be
# reviewed together with the source that produces it.


def test_local_duplicate_particle_format(
    validate_project: ValidateProject,
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
    result = validate_project({"test.dfn": source})
    diags = result.program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 8, column 30
                create a particle in position<pos>.
                                     ^
        a particle already exists in 'position<pos>'; it was put there at:
        File "test.dfn", line 7, column 30""")


def test_move_from_empty_position_format(
    validate_project: ValidateProject,
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
    result = validate_project({"test.dfn": source})
    diags = result.program_result.file_results[0].diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 8, column 30
                move the particle in position<from_pos> to position<to_pos>.
                                     ^
        cannot move a particle from 'position<from_pos>' because it does not contain one""")
    )


def test_deferred_position_chain_error_format(
    validate_project: ValidateProject,
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
    result = validate_project(
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
    assert len(result.program_result.file_results) == 3
    test_result = result.program_result.file_results[0]
    assert test_result.file_path == define_path.DefinePath("test.dfn")
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 10, column 65
                create a particle in position<pos_a>::position</pos_b>::position</wrong>.
                                                                        ^
        'position<my.domain.com:my_lib:/wrong>' must be declared as an explicit 'it has the' constraint in the definition of 'position<my.domain.com:my_lib:/pos_b>'""")
    )


def test_deferred_action_chain_error_format(
    validate_project: ValidateProject,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<pos_a> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</create_noop>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<pos_a>::action</create_noop>::position<no_such>.\n"
        "        create a particle in position<pos_a>::action</create_noop>::position<pos_c>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "create_noop.dfn": (
                "define the potential action<my.domain.com:my_lib:/create_noop> {\n"
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
    assert len(result.program_result.file_results) == 2
    test_result = result.program_result.file_results[0]
    assert test_result.file_path == define_path.DefinePath("test.dfn")
    diags = test_result.diagnostics
    assert len(diags) == 1
    formatted = diags[0].format(source.splitlines())
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 10, column 69
                create a particle in position<pos_a>::action</create_noop>::position<no_such>.
                                                                            ^
        'position<no_such>' is not an interface position of the action 'action<my.domain.com:my_lib:/create_noop>'; only that action's interface positions may follow it in a chained name""")
    )


def test_action_requires_empty_position_format(
    validate_project: ValidateProject,
):
    files = {
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
        "test.dfn": (
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
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 13, column 30
                create a particle in position<box>::action</other>::position<trigger_pos>.
                                     ^
        'position<box>::action</other>::position<item>' must be empty before 'action<my.domain.com:my_lib:/other>' runs, and it is not empty.

        This error happens because:
          'position<box>::action</other>::position<item>' is filled here:
            File "test.dfn", line 12, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/other>':
            File "test.dfn", line 13, column 30
          'action<my.domain.com:my_lib:/other>' infers this requirement:
            File "other.dfn", line 7, column 30""")
    assert action_graph_set(result.operation_graphs) == {(_TEST, _OTHER)}


def test_action_requires_occupied_position_format(
    validate_project: ValidateProject,
):
    files = {
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
        "test.dfn": (
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
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 12, column 30
                create a particle in position<box>::action</other>::position<trigger_pos>.
                                     ^
        'position<box>::action</other>::position<item>' must be occupied before 'action<my.domain.com:my_lib:/other>' runs, and it is not occupied.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/other>':
            File "test.dfn", line 12, column 30
          'action<my.domain.com:my_lib:/other>' infers this requirement:
            File "other.dfn", line 8, column 30""")


def test_propagated_action_requires_empty_position_format(
    validate_project: ValidateProject,
):
    files = {
        "inner.dfn": (
            "define the potential action<my.domain.com:my_lib:/inner> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</item_parent>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<input>::position</item_parent>::position</item>.\n"
            "    }\n"
            "}\n"
        ),
        "inner_particle.dfn": (
            "define the potential position<my.domain.com:my_lib:/inner_particle> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</item_parent>.\n"
            "    }\n"
            "}\n"
        ),
        "item.dfn": "define the potential position<my.domain.com:my_lib:/item>.\n",
        "item_parent.dfn": (
            "define the potential position<my.domain.com:my_lib:/item_parent> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</item>.\n"
            "    }\n"
            "}\n"
        ),
        "middle.dfn": (
            "define the potential action<my.domain.com:my_lib:/middle> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<mid_iface> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</inner_particle>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        define the position<inner_holder> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</inner>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<inner_holder>.\n"
            "        move the particle in position<mid_iface>::position</inner_particle> to position<inner_holder>::action</inner>::position<input>.\n"
            "        create a particle in position<inner_holder>::action</inner>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
        "middle_particle.dfn": (
            "define the potential position<my.domain.com:my_lib:/middle_particle> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</inner_particle>.\n"
            "    }\n"
            "}\n"
        ),
        "outer.dfn": (
            "define the potential action<my.domain.com:my_lib:/outer> {\n"
            "    define the position<trigger_pos>.\n"
            "    define the position<out_iface> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</middle_particle>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        define the position<middle_holder> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</middle>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<middle_holder>.\n"
            "        move the particle in position<out_iface>::position</middle_particle> to position<middle_holder>::action</middle>::position<mid_iface>.\n"
            "        create a particle in position<middle_holder>::action</middle>::position<trigger_pos>.\n"
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
            "        create a particle in position<box>::action</outer>::position<out_iface>::position</middle_particle>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>::position</middle_particle>::position</inner_particle>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>::position</middle_particle>::position</inner_particle>::position</item_parent>.\n"
            "        create a particle in position<box>::action</outer>::position<out_iface>::position</middle_particle>::position</inner_particle>::position</item_parent>::position</item>.\n"
            "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 17, column 30
                create a particle in position<box>::action</outer>::position<trigger_pos>.
                                     ^
        'position<box>::action</outer>::position<out_iface>::position</middle_particle>::position</inner_particle>::position</item_parent>::position</item>' must be empty before 'action<my.domain.com:my_lib:/outer>' runs, and it is not empty.

        This error happens because:
          'position<box>::action</outer>::position<out_iface>::position</middle_particle>::position</inner_particle>::position</item_parent>::position</item>' is filled here:
            File "test.dfn", line 16, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/outer>':
            File "test.dfn", line 17, column 30
          'action<my.domain.com:my_lib:/outer>' triggers 'action<my.domain.com:my_lib:/middle>':
            File "outer.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/middle>' triggers 'action<my.domain.com:my_lib:/inner>':
            File "middle.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/inner>' infers this requirement:
            File "inner.dfn", line 11, column 30""")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_requirement_carried_through_two_moves_format(
    validate_project: ValidateProject,
):
    files = {
        "inner.dfn": (
            "define the potential action<my.domain.com:my_lib:/inner> {\n"
            "    define the position<input>.\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<input>.\n"
            "    }\n"
            "}\n"
        ),
        "middle.dfn": (
            "define the potential action<my.domain.com:my_lib:/middle> {\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</inner>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<input>::action</inner>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
        "outer.dfn": (
            "define the potential action<my.domain.com:my_lib:/outer> {\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</inner>.\n"
            "        }\n"
            "    }\n"
            "    define the position<middle_holder> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</middle>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<middle_holder>.\n"
            "        move the particle in position<input> to position<middle_holder>::action</middle>::position<input>.\n"
            "        create a particle in position<middle_holder>::action</middle>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<box> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</inner>.\n"
            "        }\n"
            "    }\n"
            "    define the position<outer_holder> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</outer>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<outer_holder>.\n"
            "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
            "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    # The box moved through /outer into /middle never had its input filled.
    # The position names where /test sees it (through /outer's interface, not
    # the move destinations), and the chain traces both moves down to /inner's
    # inference.
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 19, column 30
                create a particle in position<outer_holder>::action</outer>::position<run>.
                                     ^
        'position<outer_holder>::action</outer>::position<input>::action</inner>::position<input>' must be occupied before 'action<my.domain.com:my_lib:/outer>' runs, and it is not occupied.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/outer>':
            File "test.dfn", line 19, column 30
          'action<my.domain.com:my_lib:/outer>' triggers 'action<my.domain.com:my_lib:/middle>':
            File "outer.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/middle>' triggers 'action<my.domain.com:my_lib:/inner>':
            File "middle.dfn", line 11, column 30
          'action<my.domain.com:my_lib:/inner>' infers this requirement:
            File "inner.dfn", line 7, column 33""")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_requirement_carried_through_actions_on_locals_format(
    validate_project: ValidateProject,
):
    files = {
        "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
        "inner.dfn": (
            "define the potential action<my.domain.com:my_lib:/inner> {\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</marker>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        destroy the particle in position<input>::position</marker>.\n"
            "    }\n"
            "}\n"
        ),
        "middle.dfn": (
            "define the potential action<my.domain.com:my_lib:/middle> {\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</marker>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<gw> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</inner>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<gw>.\n"
            "        move the particle in position<input> to position<gw>::action</inner>::position<input>.\n"
            "        create a particle in position<gw>::action</inner>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
        "outer.dfn": (
            "define the potential action<my.domain.com:my_lib:/outer> {\n"
            "    define the position<input> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</marker>.\n"
            "        }\n"
            "    }\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        define the position<mid_holder> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</middle>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<mid_holder>.\n"
            "        move the particle in position<input> to position<mid_holder>::action</middle>::position<input>.\n"
            "        create a particle in position<mid_holder>::action</middle>::position<run>.\n"
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
            "                it has the position</marker>.\n"
            "            }\n"
            "        }\n"
            "        define the position<outer_holder> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</outer>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "        create a particle in position<outer_holder>.\n"
            "        move the particle in position<box> to position<outer_holder>::action</outer>::position<input>.\n"
            "        create a particle in position<outer_holder>::action</outer>::position<run>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    # action</inner> and action</middle> exist only on body-local positions (gw
    # and mid_holder); the particle with its /marker child is passed down
    # through each action's Interface Position named input. The missing child is
    # reported on the path /test can act on, with the locals never appearing.
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 19, column 30
                create a particle in position<outer_holder>::action</outer>::position<run>.
                                     ^
        'position<outer_holder>::action</outer>::position<input>::position</marker>' must be occupied before 'action<my.domain.com:my_lib:/outer>' runs, and it is not occupied.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/outer>':
            File "test.dfn", line 19, column 30
          'action<my.domain.com:my_lib:/outer>' triggers 'action<my.domain.com:my_lib:/middle>':
            File "outer.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/middle>' triggers 'action<my.domain.com:my_lib:/inner>':
            File "middle.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/inner>' infers this requirement:
            File "inner.dfn", line 11, column 33""")
    assert action_graph_set(result.operation_graphs) == {
        (_TEST, _OUTER),
        (_OUTER, _MIDDLE),
        (_MIDDLE, _INNER),
    }


def test_move_violates_constraints_error_message(
    validate_project: ValidateProject,
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
        "                it has the action</create_noop>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<to_pos>.\n"
        "        create a particle in position<to_pos>::action</create_noop>::position<run>.\n"
        "        create a particle in position<to_pos>::position</x>.\n"
        "        destroy the particle in position<to_pos>.\n"
        "        create a particle in position<from_pos>.\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "create_noop.dfn": (
                "define the potential action<my.domain.com:my_lib:/create_noop> {\n"
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
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 18, column 52
                move the particle in position<from_pos> to position<to_pos>.
                                                           ^
        cannot move a particle
          from: position<from_pos>
            to: position<to_pos>
        because the particle being moved does not have the required qualities:
          position</x>
          action</create_noop>""")


def test_move_violates_constraints_error_message_cross_universe(
    validate_project: ValidateProject,
):
    child_fqun = "mv:define-lang.org:child"
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
        f"                it has the position<{child_fqun}:/q>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<from_pos>.\n"
        "        move the particle in position<from_pos> to position<to_pos>.\n"
        "        create a particle in position<to_pos>::position</x>.\n"
        f"        create a particle in position<to_pos>::position<{child_fqun}:/q>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "lib/q.dfn": f"define the potential position<{child_fqun}:/q>.\n",
        },
        local_deps={child_fqun: "lib"},
        sub_roots={"lib": child_fqun},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(source.splitlines())
    assert formatted == textwrap.dedent(f"""\
        File "test.dfn", line 14, column 52
                move the particle in position<from_pos> to position<to_pos>.
                                                           ^
        cannot move a particle
          from: position<from_pos>
            to: position<to_pos>
        because the particle being moved does not have the required qualities:
          position</x>
          position<{child_fqun}:/q>""")


def test_constructor_requires_empty_position_format(
    validate_project: ValidateProject,
):
    files = {
        "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
        "filler.dfn": (
            "define the potential action<my.domain.com:my_lib:/filler> {\n"
            "    it also assigns the position</q>.\n"
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
            "        create a particle in position</q>.\n"
            "    }\n"
            "}\n"
        ),
        "create_q.dfn": (
            "define the potential action<my.domain.com:my_lib:/create_q> {\n"
            "    it also assigns the position</q>.\n"
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
            "        create a particle in position</q>.\n"
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
            "                it has the action</create_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 12, column 30
                create a particle in position<box>.
                                     ^
        'position<box>::position</q>' must be empty before 'action<my.domain.com:my_lib:/create_q>' runs, and it is not empty.

        This error happens because:
          'action<my.domain.com:my_lib:/create_q>' is assigned to 'position<box>':
            File "test.dfn", line 9, column 28
          'action<my.domain.com:my_lib:/test>' creates a particle, triggering the constructor 'action<my.domain.com:my_lib:/create_q>':
            File "test.dfn", line 12, column 30
          'position<box>::position</q>' is filled here:
            File "filler.dfn", line 6, column 30
          'action<my.domain.com:my_lib:/create_q>' infers this requirement:
            File "create_q.dfn", line 6, column 30""")


def test_constructor_requires_occupied_position_format(
    validate_project: ValidateProject,
):
    files = {
        "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
        "destroy_q.dfn": (
            "define the potential action<my.domain.com:my_lib:/destroy_q> {\n"
            "    it also assigns the position</q>.\n"
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
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
            "                it has the action</destroy_q>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<box>.\n"
            "    }\n"
            "}\n"
        ),
    }
    result = validate_project(files)
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(files["test.dfn"].splitlines())
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 11, column 30
                create a particle in position<box>.
                                     ^
        'position<box>::position</q>' must be occupied before 'action<my.domain.com:my_lib:/destroy_q>' runs, and it is not occupied.

        This error happens because:
          'action<my.domain.com:my_lib:/destroy_q>' is assigned to 'position<box>':
            File "test.dfn", line 8, column 28
          'action<my.domain.com:my_lib:/test>' creates a particle, triggering the constructor 'action<my.domain.com:my_lib:/destroy_q>':
            File "test.dfn", line 11, column 30
          'action<my.domain.com:my_lib:/destroy_q>' infers this requirement:
            File "destroy_q.dfn", line 6, column 33""")


def test_destroy_in_emptied_interface_position_format(
    validate_project: ValidateProject,
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
        "        destroy the particle in position<box>.\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
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
        File "test.dfn", line 17, column 33
                destroy the particle in position<box>::action</other>::position<item>.
                                        ^
        cannot destroy a particle in 'position<box>::action</other>::position<item>' because it does not contain one; it was emptied at:
        File "test.dfn", line 16, column 33""")


def test_destroy_in_default_empty_interface_position_format(
    validate_project: ValidateProject,
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
        "        destroy the particle in position<box>.\n"
        "        create a particle in position<box>.\n"
        "        destroy the particle in position<box>::action</other>::position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
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
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 15, column 33
                destroy the particle in position<box>::action</other>::position<item>.
                                        ^
        cannot destroy a particle in 'position<box>::action</other>::position<item>' because it does not contain one; action interface positions are empty by default""")
    )


def test_move_from_emptied_interface_position_format(
    validate_project: ValidateProject,
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
        "        define the position<sink>.\n"
        "        define the position<sink2>.\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
        "        destroy the particle in position<box>.\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
        "        move the particle in position<box>::action</other>::position<item> to position<sink>.\n"
        "        move the particle in position<box>::action</other>::position<item> to position<sink2>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
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
        File "test.dfn", line 19, column 30
                move the particle in position<box>::action</other>::position<item> to position<sink2>.
                                     ^
        cannot move a particle from 'position<box>::action</other>::position<item>' because it does not contain one; it was emptied at:
        File "test.dfn", line 18, column 30""")


def test_move_from_default_empty_interface_position_format(
    validate_project: ValidateProject,
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
        "        define the position<sink>.\n"
        "        create a particle in position<box>.\n"
        "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
        "        destroy the particle in position<box>.\n"
        "        create a particle in position<box>.\n"
        "        move the particle in position<box>::action</other>::position<item> to position<sink>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
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
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 16, column 30
                move the particle in position<box>::action</other>::position<item> to position<sink>.
                                     ^
        cannot move a particle from 'position<box>::action</other>::position<item>' because it does not contain one; action interface positions are empty by default""")
    )
