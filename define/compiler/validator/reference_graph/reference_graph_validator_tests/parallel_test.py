# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph

_POSITION_WITH_REF = (
    "define the potential position<my.domain.com:my_lib:/{name}> {{\n"
    "    it may only contain dimension points where {{\n"
    "        it has the position</{ref}>.\n"
    "    }}\n"
    "}}\n"
)


def _simple_position(name: str) -> str:
    return f"define the potential position<my.domain.com:my_lib:/{name}>.\n"


def _position_with_ref(name: str, ref: str) -> str:
    return _POSITION_WITH_REF.format(name=name, ref=ref)


_MOVE_ACTION = (
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
    "                it has the position</y>.\n"
    "            }\n"
    "        }\n"
    "        create a dimension point in position<a>.\n"
    "        move the dimension point in position<a>::position</x> to position<b>::position</y>.\n"
    "    }\n"
    "}\n"
)


def _hub_with_refs(ref_lines: list[str]) -> str:
    lines = "".join(f"        {line}\n" for line in ref_lines)
    return (
        f"define the potential position<my.domain.com:my_lib:/hub> {{\n"
        f"    it may only contain dimension points where {{\n"
        f"{lines}"
        f"    }}\n"
        f"}}\n"
    )


def test_chain_element_validated_without_deferral(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "root.def": (
                "define the potential position<my.domain.com:my_lib:/root> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "        it has the action</test>.\n"
                "    }\n"
                "}\n"
            ),
            "child.def": _position_with_ref("child", "leaf"),
            "leaf.def": _simple_position("leaf"),
            "wrong.def": _simple_position("wrong"),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pos_a> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<pos_a>::position</child>::position</wrong>.\n"
                "    }\n"
                "}\n"
            ),
        },
        entry_file="root.def",
        max_workers=1,
    )
    assert len(result.program_result.file_results) == 5
    assert result.program_result.file_results[0].file_path == PurePosixPath("root.def")
    assert result.program_result.file_results[0].diagnostics == []
    assert result.program_result.file_results[1].file_path == PurePosixPath("child.def")
    assert result.program_result.file_results[1].diagnostics == []
    assert result.program_result.file_results[2].file_path == PurePosixPath("test.def")
    assert len(result.program_result.file_results[2].diagnostics) == 1
    diag = result.program_result.file_results[2].diagnostics[0]
    assert isinstance(diag, diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert diag.position.line == 10
    assert diag.position.column == 72
    assert diag.element_name == "position<my.domain.com:my_lib:/wrong>"
    assert diag.parent_name == "position<my.domain.com:my_lib:/child>"
    assert result.program_result.file_results[3].file_path == PurePosixPath("leaf.def")
    assert result.program_result.file_results[3].diagnostics == []
    assert result.program_result.file_results[4].file_path == PurePosixPath("wrong.def")
    assert result.program_result.file_results[4].diagnostics == []


def test_chain_continuation_validated_without_deferral(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "hub.def": (
                "define the potential position<my.domain.com:my_lib:/hub> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</pos_c>.\n"
                "        it has the action</test>.\n"
                "        it has the position</pos_b>.\n"
                "    }\n"
                "}\n"
            ),
            "pos_b.def": _position_with_ref("pos_b", "pos_c"),
            "pos_c.def": _simple_position("pos_c"),
            "pos_d.def": _simple_position("pos_d"),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</pos_b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pos_a> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in"
                " position<pos_a>::position</pos_b>::position</pos_c>::position</pos_d>.\n"
                "    }\n"
                "}\n"
            ),
        },
        entry_file="hub.def",
        max_workers=1,
    )
    assert len(result.program_result.file_results) == 5
    assert result.program_result.file_results[0].file_path == PurePosixPath("hub.def")
    assert result.program_result.file_results[0].diagnostics == []
    assert result.program_result.file_results[1].file_path == PurePosixPath("pos_c.def")
    assert result.program_result.file_results[1].diagnostics == []
    assert result.program_result.file_results[2].file_path == PurePosixPath("test.def")
    assert len(result.program_result.file_results[2].diagnostics) == 1
    diag = result.program_result.file_results[2].diagnostics[0]
    assert isinstance(diag, diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert diag.position.line == 10
    assert diag.position.column == 90
    assert diag.element_name == "position<my.domain.com:my_lib:/pos_d>"
    assert diag.parent_name == "position<my.domain.com:my_lib:/pos_c>"
    assert result.program_result.file_results[3].file_path == PurePosixPath("pos_b.def")
    assert result.program_result.file_results[3].diagnostics == []
    assert result.program_result.file_results[4].file_path == PurePosixPath("pos_d.def")
    assert result.program_result.file_results[4].diagnostics == []


def test_chained_to_chained_move_deferred_both_sides(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": _simple_position("x"),
            "y.def": _simple_position("y"),
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
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x> to position<b>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        },
        max_workers=1,
    )
    assert not result.program_result.has_errors()


def test_move_both_sides_resolved_immediately(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": _simple_position("x"),
            "y.def": _position_with_ref("y", "z"),
            "z.def": _simple_position("z"),
            "hub.def": _hub_with_refs(
                [
                    "it has the position</x>.",
                    "it has the position</y>.",
                    "it has the position</z>.",
                    "it has the action</test>.",
                ]
            ),
            "test.def": _MOVE_ACTION,
        },
        entry_file="hub.def",
        max_workers=1,
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 66
    assert all_diags[0].source_position == "position<a>::position</x>"
    assert all_diags[0].target_position == "position<b>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/z>",
    ]


def test_move_from_resolved_to_deferred(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": _simple_position("x"),
            "y.def": _position_with_ref("y", "z"),
            "z.def": _simple_position("z"),
            "hub.def": _hub_with_refs(
                [
                    "it has the position</x>.",
                    "it has the action</test>.",
                ]
            ),
            "test.def": _MOVE_ACTION,
        },
        entry_file="hub.def",
        max_workers=1,
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 66
    assert all_diags[0].source_position == "position<a>::position</x>"
    assert all_diags[0].target_position == "position<b>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/z>",
    ]


def test_move_from_deferred_to_resolved_on_retry(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": _simple_position("x"),
            "y.def": _position_with_ref("y", "z"),
            "z.def": _simple_position("z"),
            "hub.def": _hub_with_refs(
                [
                    "it has the position</y>.",
                    "it has the position</z>.",
                    "it has the action</test>.",
                ]
            ),
            "test.def": _MOVE_ACTION,
        },
        entry_file="hub.def",
        max_workers=1,
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 66
    assert all_diags[0].source_position == "position<a>::position</x>"
    assert all_diags[0].target_position == "position<b>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/z>",
    ]


def test_chained_to_chained_move_deferred_both_sides_violates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": _simple_position("x"),
            "y.def": _position_with_ref("y", "z"),
            "z.def": _simple_position("z"),
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
                "                it has the position</y>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<a>.\n"
                "        move the dimension point in position<a>::position</x> to position<b>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        },
        max_workers=1,
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].position.line == 17
    assert all_diags[0].position.column == 66
    assert all_diags[0].source_position == "position<a>::position</x>"
    assert all_diags[0].target_position == "position<b>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/z>",
    ]
