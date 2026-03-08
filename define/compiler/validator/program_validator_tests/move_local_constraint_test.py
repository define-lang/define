# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.validator.program_validator_tests.conftest import ValidateProject


def test_move_violates_dest_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
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
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_from_unconstrained_to_constrained(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos>.\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 13
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/x>",
    ]


def test_move_with_compatible_constraints(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<from_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_local_move_round_trip_with_constraint_subset(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "b.def": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "c.def": "define the potential position<my.domain.com:my_lib:/c>.\n",
            "d.def": "define the potential position<my.domain.com:my_lib:/d>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</b>.\n"
                "                it has the position</c>.\n"
                "                it has the position</d>.\n"
                "            }\n"
                "        }\n"
                "        define the position<b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</b>.\n"
                "                it has the position</c>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a> to position<b>.\n"
                "        move the dimension point in position<b> to position<a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_local_move_violates_constraints_marks_unknown(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
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
                "        define the position<to_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "        create a dimension point in position<from_pos>.\n"
                "        create a dimension point in position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 59
    assert all_diags[0].from_position == "position<from_pos>"
    assert all_diags[0].to_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_move_to_unconstrained_position(validate_project: ValidateProject):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
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
                "        define the position<to_pos>.\n"
                "        create a dimension point in position<from_pos>.\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_definition_local_to_statement_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<def_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<def_pos> to position<stmt_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 15
    assert all_diags[0].position.column == 58
    assert all_diags[0].from_position == "position<def_pos>"
    assert all_diags[0].to_position == "position<stmt_pos>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_definition_local_to_statement_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<def_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<def_pos> to position<stmt_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_statement_local_to_definition_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<stmt_pos>.\n"
                "        move the dimension point in position<stmt_pos> to position<def_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_statement_local_to_definition_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<def_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<stmt_pos> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<stmt_pos>.\n"
                "        move the dimension point in position<stmt_pos> to position<def_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_definition_local_to_definition_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<to_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/y>",
    ]


def test_definition_local_to_definition_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<from_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<to_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<from_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<from_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []
