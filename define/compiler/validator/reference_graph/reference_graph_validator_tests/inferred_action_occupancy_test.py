# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.conftest import ValidateNonFilesystemWithReferenceGraph


def test_move_source_requirement_satisfied_no_error(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    define the position<dest>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<item> to position<dest>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert not result.has_errors()


def test_create_target_requirement_satisfied_no_error(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert not result.has_errors()


def test_interface_position_first_used_as_move_source_then_create_is_valid(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    define the position<other>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        move the dimension point in position<item> to position<other>.\n"
        "        create a dimension point in position<item>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert not result.has_errors()


def test_interface_position_first_used_as_create_then_move_is_valid(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    define the position<item>.\n"
        "    define the position<other>.\n"
        "    it happens when {\n"
        "        the position<run> has a dimension point.\n"
        "    } and it does {\n"
        "        create a dimension point in position<item>.\n"
        "        move the dimension point in position<item> to position<other>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert not result.has_errors()


def test_move_from_interface_chained_to_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest>.\n"
                "        move the dimension point in position<iface>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_move_from_local_to_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<src>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src> to position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_move_between_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "y.def": "define the potential position<my.domain.com:my_lib:/y>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<src_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</y>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<src_iface> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<src_iface>::position</x> to position<dest_iface>::position</y>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_move_to_occupied_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<src>.\n"
                "        create a dimension point in position<src>.\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "        move the dimension point in position<src> to position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 54
    assert all_diags[0].location.file_path == PurePosixPath("test.def")
    assert all_diags[0].position_name == "position<iface>::position</x>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 12
    assert all_diags[0].occupied_at.column == 37
    assert all_diags[0].occupied_at.file_path == PurePosixPath("test.def")


def test_create_in_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_create_twice_in_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.def")
    assert all_diags[0].position_name == "position<iface>::position</x>"
    assert all_diags[0].created_at.line == 10
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("test.def")


def test_move_then_create_in_interface_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<iface> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest>.\n"
                "        move the dimension point in position<iface>::position</x> to position<dest>.\n"
                "        create a dimension point in position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_move_from_trigger_chained_to_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_create_in_trigger_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()


def test_create_twice_in_trigger_chained(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.def")
    assert all_diags[0].position_name == "position<trigger_pos>::position</x>"
    assert all_diags[0].created_at.line == 10
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("test.def")


def test_move_from_trigger_chained_then_create(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<dest>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<dest>.\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert not result.program_result.has_errors()
