# pyright: reportUnusedCallResult=false

from define.compiler import conftest, diagnostics

_PARENT = "mv:define-lang.org:parent"
_CHILD = "mv:define-lang.org:child"


def test_cross_fqun_local_to_local_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": f"define the potential position<{_CHILD}:/x>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<from_pos> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        define the position<to_pos> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<from_pos>.\n"
                f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    assert not result.program_result.has_errors()


def test_cross_fqun_local_to_local_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": f"define the potential position<{_CHILD}:/x>.\n",
            "lib/y.def": f"define the potential position<{_CHILD}:/y>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<from_pos> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        define the position<to_pos> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/y>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<from_pos>.\n"
                f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_local_to_chained_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": (
                f"define the potential position<{_CHILD}:/x> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</y>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/y.def": f"define the potential position<{_CHILD}:/y>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<from_pos> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/y>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<from_pos>.\n"
                f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    assert not result.program_result.has_errors()


def test_cross_fqun_local_to_chained_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": (
                f"define the potential position<{_CHILD}:/x> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</y>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/y.def": f"define the potential position<{_CHILD}:/y>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<from_pos>.\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<from_pos>.\n"
                f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_chained_to_local_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": (
                f"define the potential position<{_CHILD}:/x> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</y>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/y.def": f"define the potential position<{_CHILD}:/y>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/y>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    assert not result.program_result.has_errors()


def test_cross_fqun_chained_to_local_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/x.def": f"define the potential position<{_CHILD}:/x>.\n",
            "lib/y.def": f"define the potential position<{_CHILD}:/y>.\n",
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/x>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/y>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_move_to_chained_action_local_satisfies(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<local_dest> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the position</quality>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/quality>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src> to action<{_CHILD}:/act>::position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    assert not result.program_result.has_errors()


def test_cross_fqun_move_to_chained_action_local_violates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<local_dest> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the position</quality>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src>.\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src> to action<{_CHILD}:/act>::position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/quality>",
    ]


def test_cross_fqun_move_from_chained_nonexistent_local_to_constrained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<inner>.\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<inner>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    define the position<src> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the action<{_CHILD}:/act>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/quality>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src>::action<{_CHILD}:/act>::position<no_such> to position<dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == f"action<{_CHILD}:/act>"
    assert isinstance(all_diags[1], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[1].missing_qualities == [
        f"position<{_CHILD}:/quality>",
    ]
