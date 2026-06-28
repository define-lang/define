# pyright: reportUnusedCallResult=false

# Destruction-related error-message snapshot tests, split out from the general
# reference-graph error messages: destructor requirements, destructor
# guarantees, auto-destruction, and Destruction Contracts.

import textwrap

from define.compiler.conftest import ValidateProjectWithReferenceGraph


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
        'position<box>::position</child_q>::action</destructor>::position<item>' must be occupied before 'action<my.domain.com:my_lib:/destructor>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child_q>':
            File "child_q.dfn", line 3, column 20
          the particle in 'position<box>::position</child_q>' comes from here:
            File "test.dfn", line 17, column 30
          'action<my.domain.com:my_lib:/test>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor>':
            File "test.dfn", line 19, column 33
          'action<my.domain.com:my_lib:/destructor>' infers this requirement:
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
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before 'action<my.domain.com:my_lib:/destructor_empty>' runs, and it is not empty.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/destructor_empty>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child_q>':
            File "child_q.dfn", line 3, column 20
          the particle in 'position<box>::position</child_q>' comes from here:
            File "test.dfn", line 17, column 30
          'position<box>::position</child_q>::action</destructor_empty>::position<item>' is filled here:
            File "test.dfn", line 19, column 30
          'action<my.domain.com:my_lib:/test>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "test.dfn", line 20, column 33
          'action<my.domain.com:my_lib:/destructor_empty>' infers this requirement:
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
        'position<box>::action</close_file>::position<target>::position</file>' must be occupied before 'action<my.domain.com:my_lib:/close_file>' runs, and it is not occupied.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/close_file>':
            File "test.dfn", line 13, column 30
          the destructor 'action<my.domain.com:my_lib:/destructor>' is attached to the particle by a constraint on 'position<target>':
            File "close_file.dfn", line 4, column 24
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor>':
            File "close_file.dfn", line 11, column 33
          'action<my.domain.com:my_lib:/destructor>' infers this requirement:
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
    assert (
        all_diags[0].format(test_source.splitlines())
        == textwrap.dedent("""\
        File "test.dfn", line 16, column 30
                move the particle in position<incoming> to position<tmp>.
                                     ^
        a destructor must leave every position in the state it was in when it started.
        However, this line empties 'position<incoming>' and then nothing puts the same particle back into that position.""")
    )
    assert (
        all_diags[1].format(test_source.splitlines())
        == textwrap.dedent("""\
        File "test.dfn", line 17, column 65
                move the particle in position<tmp>::position</child> to position<dest>.
                                                                        ^
        a destructor must leave every position in the state it was in when it started.
        However, this line moves a particle from 'position<incoming>::position</child>' into 'position<dest>' and then nothing moves it back out of that position.""")
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
    assert (
        all_diags[0].format(test_source.splitlines())
        == textwrap.dedent("""\
        File "test.dfn", line 6, column 30
                create a particle in position<item>.
                                     ^
        a destructor must leave every position in the state it was in when it started.
        However, this line creates a new particle in 'position<item>' and then nothing removes it from that position.""")
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
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before 'action<my.domain.com:my_lib:/destructor_empty>' runs, and it is not empty.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/destructor_empty>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child_q>':
            File "child_q.dfn", line 3, column 20
          the particle in 'position<box>::position</child_q>' comes from here:
            File "test.dfn", line 17, column 30
          'position<box>::position</child_q>::action</destructor_empty>::position<item>' is filled here:
            File "test.dfn", line 19, column 30
          the particle in 'position<box>' is automatically destroyed at the end of 'action<my.domain.com:my_lib:/test>':
            File "test.dfn", line 18, column 51
          'action<my.domain.com:my_lib:/test>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "test.dfn", line 18, column 51
          'action<my.domain.com:my_lib:/destructor_empty>' infers this requirement:
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
        'position<box>::position</child_q>::action</destructor>::position<item>' must be occupied before 'action<my.domain.com:my_lib:/destructor>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child_q>':
            File "child_q.dfn", line 3, column 20
          the particle in 'position<box>::position</child_q>' comes from here:
            File "test.dfn", line 17, column 30
          the particle in 'position<box>' is automatically destroyed at the end of 'action<my.domain.com:my_lib:/test>':
            File "test.dfn", line 18, column 51
          'action<my.domain.com:my_lib:/test>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor>':
            File "test.dfn", line 18, column 51
          'action<my.domain.com:my_lib:/destructor>' infers this requirement:
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
        'position<box>::position</child_q>::action</destructor_empty>::position<item>' must be empty before 'action<my.domain.com:my_lib:/destructor_empty>' runs, and it is not empty.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/destructor_empty>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child_q>':
            File "child_q.dfn", line 3, column 20
          the particle in 'position<box>::position</child_q>' comes from here:
            File "test.dfn", line 14, column 30
          'position<box>::position</child_q>::action</destructor_empty>::position<item>' is filled here:
            File "test.dfn", line 16, column 30
          the particle in 'position<box>' is automatically destroyed at the end of 'position<my.domain.com:my_lib:/test>':
            File "test.dfn", line 15, column 51
          'position<my.domain.com:my_lib:/test>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "test.dfn", line 15, column 51
          'action<my.domain.com:my_lib:/destructor_empty>' infers this requirement:
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
        'position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>' must be empty before 'action<my.domain.com:my_lib:/inner>' runs, and it is not empty.

        This error happens because:
          'position<box>::action</inner>::position<incoming>::action</destructor_empty>::position<item>' is filled here:
            File "test.dfn", line 13, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/inner>':
            File "test.dfn", line 14, column 30
          the destructor 'action<my.domain.com:my_lib:/destructor_empty>' is attached to the particle by a constraint on 'position<incoming>':
            File "inner.dfn", line 4, column 24
          'action<my.domain.com:my_lib:/inner>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "inner.dfn", line 11, column 9
          'action<my.domain.com:my_lib:/destructor_empty>' infers this requirement:
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
            "        create a particle in position<box>::position</p>.\n"
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
        'position<box>::position</q>::action</destructor_empty>::position<item>' must be empty before the Position Initialization Block of 'position<my.domain.com:my_lib:/p>' runs, and it is not empty.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' creates a particle that runs the Position Initialization Block of 'position<my.domain.com:my_lib:/p>':
            File "test.dfn", line 11, column 30
          the destructor 'action<my.domain.com:my_lib:/destructor_empty>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/q>':
            File "q.dfn", line 3, column 20
          'position<box>::position</q>::action</destructor_empty>::position<item>' is filled here:
            File "q.dfn", line 7, column 30
          'position<my.domain.com:my_lib:/p>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/destructor_empty>':
            File "p.dfn", line 4, column 33
          'action<my.domain.com:my_lib:/destructor_empty>' infers this requirement:
            File "destructor_empty.dfn", line 6, column 30""")


# --- Destruction Contract stacks (DLP 41) ---
#
# These cover the new error stacks where the destroying action could NOT see a
# caller-attached destructor and recorded a Destruction Contract that the
# triggering action verifies. The chain gains a DESTRUCTOR_ATTACHED step (the
# attacher) after the DESTRUCTOR_CASCADE step (the destroyer): destruction comes
# before attachment, as a causal stack.


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
        'position<box>::action</close_file>::position<target>::position</file>' must be occupied before 'action<my.domain.com:my_lib:/close_file>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/delete_file_destructor>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 14, column 28
          the particle in 'position<box>::action</close_file>::position<target>' comes from here:
            File "test.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/close_file>':
            File "test.dfn", line 20, column 30
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_file_destructor>':
            File "close_file.dfn", line 11, column 33
          'action<my.domain.com:my_lib:/delete_file_destructor>' infers this requirement:
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
        'position<box>::action</filler>::position<incoming>::position</p2>' must be empty before 'action<my.domain.com:my_lib:/filler>' runs, and it is not empty.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/d>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 13, column 28
          the particle in 'position<box>::action</filler>::position<incoming>' comes from here:
            File "test.dfn", line 17, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/filler>':
            File "test.dfn", line 19, column 30
          'position<box>::action</filler>::position<incoming>::position</p2>' is filled here:
            File "filler.dfn", line 17, column 30
          'action<my.domain.com:my_lib:/filler>' triggers 'action<my.domain.com:my_lib:/close_file>':
            File "filler.dfn", line 19, column 30
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/d>':
            File "close_file.dfn", line 7, column 33
          'action<my.domain.com:my_lib:/d>' infers this requirement:
            File "d.dfn", line 6, column 30""")


# TODO: The auto-destruction step still names 'position<local_box>', a local
# position inside mid that does not appear in the pointed-at line. A future
# change should show the stack of positional moves that carried the particle to
# where it was auto-destroyed.
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
        File "test.dfn", line 20, column 30
                create a particle in position<box>::action</mid>::position<run>.
                                     ^
        'position<box>::action</mid>::position<incoming>::position</file>' must be occupied before 'action<my.domain.com:my_lib:/mid>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/delete_destructor>' is attached to the particle by a constraint on 'position<my_file>':
            File "test.dfn", line 14, column 28
          the particle in 'position<box>::action</mid>::position<incoming>' comes from here:
            File "test.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/mid>':
            File "test.dfn", line 20, column 30
          the particle in 'position<local_box>' is automatically destroyed at the end of 'action<my.domain.com:my_lib:/mid>':
            File "mid.dfn", line 11, column 9
          'action<my.domain.com:my_lib:/mid>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_destructor>':
            File "mid.dfn", line 11, column 9
          'action<my.domain.com:my_lib:/delete_destructor>' infers this requirement:
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
        'position<box>::action</close_file>::position<target>::position</file>' must be occupied before 'action<my.domain.com:my_lib:/close_file>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/delete_destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/carrier>':
            File "carrier.dfn", line 4, column 20
          the particle in 'position<box>::action</close_file>::position<target>' comes from here:
            File "test.dfn", line 10, column 30
          'position<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/close_file>':
            File "test.dfn", line 12, column 30
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/delete_destructor>':
            File "close_file.dfn", line 11, column 33
          'action<my.domain.com:my_lib:/delete_destructor>' infers this requirement:
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
        'position<box>::action</close_file>::position<target>::position</child>::position</file>' must be occupied before 'action<my.domain.com:my_lib:/close_file>' runs, and it is not occupied.

        This error happens because:
          the destructor 'action<my.domain.com:my_lib:/child_destructor>' is attached to the particle by a constraint on 'position<my.domain.com:my_lib:/child>':
            File "child.dfn", line 3, column 20
          the particle in 'position<box>::action</close_file>::position<target>::position</child>' comes from here:
            File "test.dfn", line 18, column 30
          'action<my.domain.com:my_lib:/test>' triggers 'action<my.domain.com:my_lib:/close_file>':
            File "test.dfn", line 20, column 30
          'action<my.domain.com:my_lib:/close_file>' destroys a particle, triggering the destructor 'action<my.domain.com:my_lib:/child_destructor>':
            File "close_file.dfn", line 7, column 33
          'action<my.domain.com:my_lib:/child_destructor>' infers this requirement:
            File "child_destructor.dfn", line 7, column 30""")
