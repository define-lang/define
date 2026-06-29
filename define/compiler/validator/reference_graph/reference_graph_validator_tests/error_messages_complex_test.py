# pyright: reportUnusedCallResult=false
"""A Destruction Contract whose destruction happens many trigger hops away.

A particle carrying two destructors (d1, d2) is passed down a long chain of
action triggers and destroyed at the bottom, where both destructors fire with
unmet requirements (p1 is filled, so d1's empty-requirement is violated; p2 is
emptied, so d2's occupied-requirement is violated). The chain must trace every
trigger hop from the verifying definition down to the destruction, the same way
ordinary requirement propagation does.
"""

import textwrap

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_OUTER_IMPLIED = "action<my.domain.com:my_lib:/outer_implied>"
_TRIGGERED_BY_OUTER_IMPLIED = "action<my.domain.com:my_lib:/triggered_by_outer_implied>"
_DO_NOTHING = "action<my.domain.com:my_lib:/do_nothing>"
_EMPTY_P2 = "action<my.domain.com:my_lib:/empty_p2>"
_BEFORE_DESTRUCTOR = "action<my.domain.com:my_lib:/before_destructor>"
_DO_DESTRUCTION = "action<my.domain.com:my_lib:/do_destruction>"
_D1 = "action<my.domain.com:my_lib:/d1>"
_D2 = "action<my.domain.com:my_lib:/d2>"

_FILES = {
    "p1.dfn": "define the potential position<my.domain.com:my_lib:/p1>.\n",
    "p2.dfn": "define the potential position<my.domain.com:my_lib:/p2>.\n",
    "d1.dfn": (
        "define the potential action<my.domain.com:my_lib:/d1> {\n"
        "    it also assigns the position</p1>.\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        create a particle in position</p1>.\n"
        "        destroy the particle in position</p1>.\n"
        "    }\n"
        "}\n"
    ),
    "d2.dfn": (
        "define the potential action<my.domain.com:my_lib:/d2> {\n"
        "    it also assigns the position</p2>.\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_holder>.\n"
        "        move the particle in position</p2> to position<_holder>.\n"
        "        move the particle in position<_holder> to position</p2>.\n"
        "    }\n"
        "}\n"
    ),
    "holder.dfn": (
        "define the potential action<my.domain.com:my_lib:/holder> {\n"
        "    define the position<iface> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</d1>.\n"
        "            it has the action</d2>.\n"
        "            it has the position</p1>.\n"
        "            it has the position</p2>.\n"
        "        }\n"
        "    }\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_holder>.\n"
        "        move the particle in position<iface> to position<_holder>.\n"
        "        move the particle in position<_holder> to position<iface>.\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    ),
    # outer_implied's interface position knows d1 (but not d2), so it is the
    # first definition that hides d1 once it moves the particle on to
    # triggered_by_outer_implied, which knows neither destructor.
    "outer_implied.dfn": (
        "define the potential action<my.domain.com:my_lib:/outer_implied> {\n"
        "    it also assigns the action</triggered_by_outer_implied>.\n"
        "    define the position<incoming> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</d1>.\n"
        "            it has the position</p1>.\n"
        "            it has the position</p2>.\n"
        "        }\n"
        "    }\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<incoming> to action</triggered_by_outer_implied>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    "triggered_by_outer_implied.dfn": (
        "define the potential action<my.domain.com:my_lib:/triggered_by_outer_implied> {\n"
        "    it also assigns the action</do_nothing>.\n"
        "    define the position<trigger_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</p1>.\n"
        "            it has the position</p2>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<trigger_pos>::position</p1>.\n"
        "        move the particle in position<trigger_pos> to action</do_nothing>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    "do_nothing.dfn": (
        "define the potential action<my.domain.com:my_lib:/do_nothing> {\n"
        "    it also assigns the action</empty_p2>.\n"
        "    define the position<trigger_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</p2>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<trigger_pos> to action</empty_p2>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    "empty_p2.dfn": (
        "define the potential action<my.domain.com:my_lib:/empty_p2> {\n"
        "    it also assigns the action</before_destructor>.\n"
        "    define the position<trigger_pos> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</p2>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<trigger_pos>::position</p2>.\n"
        "        destroy the particle in position<trigger_pos>::position</p2>.\n"
        "        move the particle in position<trigger_pos> to action</before_destructor>::position<trigger_pos>.\n"
        "    }\n"
        "}\n"
    ),
    "before_destructor.dfn": (
        "define the potential action<my.domain.com:my_lib:/before_destructor> {\n"
        "    it also assigns the action</do_destruction>.\n"
        "    define the position<trigger_pos>.\n"
        "    it happens when {\n"
        "        the position<trigger_pos> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in position<trigger_pos> to action</do_destruction>::position<to_destroy>.\n"
        "        create a particle in action</do_destruction>::position<run>.\n"
        "    }\n"
        "}\n"
    ),
    "do_destruction.dfn": (
        "define the potential action<my.domain.com:my_lib:/do_destruction> {\n"
        "    define the position<to_destroy>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        destroy the particle in position<to_destroy>.\n"
        "    }\n"
        "}\n"
    ),
    # /outer moves the carrier out of holder::iface (where it can still see d2)
    # into outer_implied::incoming (which hides d2), so /outer is the first
    # caller that must verify d2. It then triggers outer_implied.
    "outer.dfn": (
        "define the potential action<my.domain.com:my_lib:/outer> {\n"
        "    it also assigns the action</holder>.\n"
        "    it also assigns the action</outer_implied>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        move the particle in action</holder>::position<iface> to action</outer_implied>::position<incoming>.\n"
        "        create a particle in action</outer_implied>::position<run>.\n"
        "    }\n"
        "}\n"
    ),
    "test.dfn": (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it also assigns the action</holder>.\n"
        "    it also assigns the action</outer>.\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in action</holder>::position<iface>.\n"
        "        create a particle in action</outer>::position<run>.\n"
        "    }\n"
        "}\n"
    ),
}


def test_destruction_contract_traces_every_trigger_hop(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(_FILES)
    # Per the Destruction Contract rules, each destructor is verified by the first
    # caller up the stack that knows it is on the particle: d1 by outer_implied
    # (whose incoming position declares it), and d2 by /outer (which moved the
    # particle out of holder::iface). So both destructors must fire
    # (do_destruction -> d1 and do_destruction -> d2).
    assert result.action_call_graph.edges() == [
        (_BEFORE_DESTRUCTOR, _DO_DESTRUCTION),
        (_DO_DESTRUCTION, _D1),
        (_DO_DESTRUCTION, _D2),
        (_EMPTY_P2, _BEFORE_DESTRUCTOR),
        (_DO_NOTHING, _EMPTY_P2),
        (_TRIGGERED_BY_OUTER_IMPLIED, _DO_NOTHING),
        (_OUTER_IMPLIED, _TRIGGERED_BY_OUTER_IMPLIED),
        (_OUTER, _OUTER_IMPLIED),
        (_TEST, _OUTER),
    ]
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    violations = [
        d
        for d in all_diags
        if isinstance(d, diagnostics.InferredRequirementViolationDiagnostic)
    ]
    assert len(violations) == 2
    by_state = {d.required_empty: d for d in violations}
    d2_diag = by_state[False]
    d1_diag = by_state[True]

    # d1 is hidden from every trigger position below outer_implied::incoming, so
    # its contract is verified at outer_implied (the first caller that knows d1).
    # The full chain must trace all four trigger hops down to 'do_destruction'.
    assert d1_diag.format(_FILES["outer_implied.dfn"].splitlines()) == textwrap.dedent("""\
        File "outer_implied.dfn", line 14, column 52
                move the particle in position<incoming> to action</triggered_by_outer_implied>::position<trigger_pos>.
                                                           ^
        'action</triggered_by_outer_implied>::position<trigger_pos>::position</p1>' must be empty before 'action<my.domain.com:my_lib:/triggered_by_outer_implied>' runs, and it is not empty.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/d1>' is attached to the particle by a constraint on 'position<incoming>':
            File "outer_implied.dfn", line 5, column 24
          the particle in 'action</triggered_by_outer_implied>::position<trigger_pos>' comes from here:
            File "outer_implied.dfn", line 14, column 30
          'action<my.domain.com:my_lib:/outer_implied>' triggers 'action<my.domain.com:my_lib:/triggered_by_outer_implied>':
            File "outer_implied.dfn", line 14, column 52
          'action</triggered_by_outer_implied>::position<trigger_pos>::position</p1>' is filled here:
            File "triggered_by_outer_implied.dfn", line 12, column 30
          'action<my.domain.com:my_lib:/triggered_by_outer_implied>' triggers 'action<my.domain.com:my_lib:/do_nothing>':
            File "triggered_by_outer_implied.dfn", line 13, column 55
          'action<my.domain.com:my_lib:/do_nothing>' triggers 'action<my.domain.com:my_lib:/empty_p2>':
            File "do_nothing.dfn", line 11, column 55
          'action<my.domain.com:my_lib:/empty_p2>' triggers 'action<my.domain.com:my_lib:/before_destructor>':
            File "empty_p2.dfn", line 13, column 55
          'action<my.domain.com:my_lib:/before_destructor>' triggers 'action<my.domain.com:my_lib:/do_destruction>':
            File "before_destructor.dfn", line 8, column 30
          'action<my.domain.com:my_lib:/do_destruction>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/d1>':
            File "do_destruction.dfn", line 7, column 33
          'action<my.domain.com:my_lib:/d1>' infers this requirement:
            File "d1.dfn", line 6, column 30""")

    # d2 is invisible everywhere below holder::iface, so the first caller that
    # knows it is /outer (which moved the particle out of holder::iface). d2 must
    # therefore be verified at /outer, with the attachment traced back to the
    # holder::iface constraint and the chain running through every trigger hop
    # down to 'do_destruction'.
    assert d2_diag.format(_FILES["outer.dfn"].splitlines()) == textwrap.dedent("""\
        File "outer.dfn", line 9, column 30
                create a particle in action</outer_implied>::position<run>.
                                     ^
        'action</outer_implied>::position<incoming>::position</p2>' must be occupied before 'action<my.domain.com:my_lib:/outer_implied>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/d2>' is attached to the particle by a constraint on 'position<iface>':
            File "holder.dfn", line 5, column 24
          the particle in 'action</outer_implied>::position<incoming>' comes from here:
            File "outer.dfn", line 8, column 30
          'action<my.domain.com:my_lib:/outer>' triggers 'action<my.domain.com:my_lib:/outer_implied>':
            File "outer.dfn", line 9, column 30
          'action<my.domain.com:my_lib:/outer_implied>' triggers 'action<my.domain.com:my_lib:/triggered_by_outer_implied>':
            File "outer_implied.dfn", line 14, column 52
          'action<my.domain.com:my_lib:/triggered_by_outer_implied>' triggers 'action<my.domain.com:my_lib:/do_nothing>':
            File "triggered_by_outer_implied.dfn", line 13, column 55
          'action<my.domain.com:my_lib:/do_nothing>' triggers 'action<my.domain.com:my_lib:/empty_p2>':
            File "do_nothing.dfn", line 11, column 55
          'action<my.domain.com:my_lib:/empty_p2>' triggers 'action<my.domain.com:my_lib:/before_destructor>':
            File "empty_p2.dfn", line 13, column 55
          'action<my.domain.com:my_lib:/before_destructor>' triggers 'action<my.domain.com:my_lib:/do_destruction>':
            File "before_destructor.dfn", line 8, column 30
          'action<my.domain.com:my_lib:/do_destruction>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/d2>':
            File "do_destruction.dfn", line 7, column 33
          'action<my.domain.com:my_lib:/d2>' infers this requirement:
            File "d2.dfn", line 7, column 30""")
