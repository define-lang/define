# pyright: reportUnusedCallResult=false

from define.compiler import conftest, diagnostics
from define.compiler.conftest import ValidateNonFilesystemWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_move_to_chained_dest_violates_constraints(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<from_pos>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_to_chained_dest_satisfies_constraints(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<from_pos>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_to_chained_dest_unconstrained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<from_pos>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_chained_to_local_violates_constraints(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<b>.\n"
                "        move the particle in position<a> to position<b>::position</x>.\n"
                "        move the particle in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_from_chained_to_local_satisfies_constraints(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<b>.\n"
                "        move the particle in position<a> to position<b>::position</x>.\n"
                "        move the particle in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_unconstrained_local_to_chained_constrained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<from_pos>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "        the position<from_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_chained_to_definition_local_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<b>.\n"
                "        move the particle in position<a> to position<b>::position</x>.\n"
                "        move the particle in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_chained_to_definition_local_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<b>.\n"
                "        move the particle in position<a> to position<b>::position</x>.\n"
                "        move the particle in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_multi_element_chain_to_unconstrained_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<a>.\n"
                "        create a particle in position<src>.\n"
                "        create a particle in position<src>::position</x>.\n"
                "        create a particle in position<src>::position</x>::position</y>.\n"
                "        move the particle in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_multi_element_chain_to_constrained_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</z>.\n"
                "    }\n"
                "}\n"
            ),
            "z.dfn": "define the potential position<my.domain.com:my_lib:/z>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<src>.\n"
                "        create a particle in position<src>::position</x>.\n"
                "        create a particle in position<src>::position</x>::position</y>.\n"
                "        move the particle in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_three_element_chain_to_three_element_chain_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.dfn": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<a>::position</x>.\n"
                "        create a particle in position<a>::position</x>::position</y>.\n"
                "        create a particle in position<b>.\n"
                "        create a particle in position<b>::position</z>.\n"
                "        move the particle in position<a>::position</x>::position</y> to position<b>::position</z>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_three_element_chain_to_three_element_chain_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.dfn": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.dfn": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</w>.\n"
                "    }\n"
                "}\n"
            ),
            "w.dfn": (
                "define the potential position<my.domain.com:my_lib:/w> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<a>.\n"
                "        create a particle in position<a>::position</x>.\n"
                "        create a particle in position<a>::position</x>::position</y>.\n"
                "        create a particle in position<b>.\n"
                "        create a particle in position<b>::position</z>.\n"
                "        move the particle in position<a>::position</x>::position</y> to position<b>::position</z>::position</w>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].source_position == "position<a>::position</x>::position</y>"
    assert all_diags[0].target_position == "position<b>::position</z>::position</w>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_from_local_local_chain(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    it happens when {\n"
        "        the position<a> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<b>.\n"
        "        move the particle in position<a>::position<b> to position<c>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    results = result.file_results
    assert len(results[0].diagnostics) == 1
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )


def test_move_from_local_local_local_chain(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    define the position<d>.\n"
        "    it happens when {\n"
        "        the position<a> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<b>.\n"
        "        create a particle in position<c>.\n"
        "        move the particle in position<a>::position<b>::position<c> to position<d>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    results = result.file_results
    assert len(results[0].diagnostics) == 2
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
