# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.structural import program_validator


def test_move_to_chained_dest_violates_constraints(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            # TODO: This should be failing because there is no DP in position<dest>.
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_to_chained_dest_satisfies_constraints(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_to_chained_dest_unconstrained(validate_project: ValidateProject):
    result = validate_project(
        {
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_from_chained_to_local_violates_constraints(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_from_chained_to_local_satisfies_constraints(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "q.def": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<c> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<c>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_from_unconstrained_local_to_chained_constrained(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_violates(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos>.\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_definition_local_to_chained_satisfies(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<from_pos> to position<dest>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_chained_to_definition_local_violates(validate_project: ValidateProject):
    result = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_chained_to_definition_local_satisfies(validate_project: ValidateProject):
    result = validate_project(
        {
            "q.def": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q>.\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>::position</x>.\n"
                "        move the dimension point in position<b>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_from_multi_element_chain_to_unconstrained_local(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<a>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_from_multi_element_chain_to_constrained_local(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": (
                "define the potential position<my.domain.com:my_lib:/y> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</z>.\n"
                "    }\n"
                "}\n"
            ),
            "z.def": "define the potential position<my.domain.com:my_lib:/z>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src>::position</x>::position</y> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_three_element_chain_to_three_element_chain_satisfies(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.def": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x>::position</y> to position<b>::position</z>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.has_errors()


def test_move_three_element_chain_to_three_element_chain_violates(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "x.def": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</y>.\n"
                "    }\n"
                "}\n"
            ),
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "z.def": (
                "define the potential position<my.domain.com:my_lib:/z> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</w>.\n"
                "    }\n"
                "}\n"
            ),
            "w.def": (
                "define the potential position<my.domain.com:my_lib:/w> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</z>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x>::position</y> to position<b>::position</z>::position</w>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].source_position == "position<a>::position</x>::position</y>"
    assert all_diags[0].target_position == "position<b>::position</z>::position</w>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_from_local_local_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    it happens when {\n"
        "        the position<a> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<a>::position<b> to position<c>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert len(results[0].diagnostics) == 2
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    )


def test_move_from_local_local_local_chain():
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<a>.\n"
        "    define the position<b>.\n"
        "    define the position<c>.\n"
        "    define the position<d>.\n"
        "    it happens when {\n"
        "        the position<a> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<a>::position<b>::position<c> to position<d>.\n"
        "    }\n"
        "}\n"
    )
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    assert len(results[0].diagnostics) == 3
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    )
    assert isinstance(
        results[0].diagnostics[2],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
