from pathlib import PurePosixPath

from define.compiler import ast, diagnostics

_POS = ast.SourcePosition(line=3, column=5, end_line=3, end_column=12)


def test_circular_reference_message_lists_each_name():
    diagnostic = diagnostics.CircularGlobalReferenceDiagnostic(
        location=_POS,
        cycle=[
            "position<my.domain.com:my_lib:/a>",
            "position<my.domain.com:my_lib:/b>",
            "action<my.domain.com:my_lib:/c>",
        ],
    )

    assert diagnostic.message == (
        "circular references between definitions are not allowed in Define:\n"
        "position<my.domain.com:my_lib:/a>\n"
        "  --> position<my.domain.com:my_lib:/b>\n"
        "  --> action<my.domain.com:my_lib:/c>"
    )


def test_move_to_occupied_message_without_line_number():
    diagnostic = diagnostics.MoveToOccupiedPositionDiagnostic(
        location=_POS,
        position_name="position<target>",
    )

    assert diagnostic.message == (
        "cannot move a dimension point to 'position<target>'"
        " because it already contains one"
    )


def test_move_to_occupied_message_with_position():
    diagnostic = diagnostics.MoveToOccupiedPositionDiagnostic(
        location=_POS,
        position_name="position<target>",
        occupied_at=ast.SourcePosition(
            line=9,
            column=37,
            end_line=9,
            end_column=37,
            file_path=PurePosixPath("test.dfn"),
        ),
    )

    assert diagnostic.message == (
        "cannot move a dimension point to 'position<target>'"
        " because it already contains one; it was put there at:\n"
        'File "test.dfn", line 9, column 37'
    )


def test_move_from_empty_interface_position_default():
    diagnostic = diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
        location=_POS,
        position_name="position<box>::action</other>::position<item>",
        inferred_at=None,
    )

    assert diagnostic.message == (
        "cannot move a dimension point from"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one;"
        " action interface positions are empty by default"
    )


def test_move_from_empty_interface_position_with_inferred_at():
    diagnostic = diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
        location=_POS,
        position_name="position<box>::action</other>::position<trigger_pos>",
        inferred_at=ast.SourcePosition(
            line=7,
            column=37,
            end_line=7,
            end_column=37,
            file_path=PurePosixPath("other.dfn"),
        ),
    )

    assert diagnostic.message == (
        "cannot move a dimension point from"
        " 'position<box>::action</other>::position<trigger_pos>'"
        " because it does not contain one; it was emptied at:\n"
        'File "other.dfn", line 7, column 37'
    )


def test_formatted_inferred_at_without_propagation():
    diagnostic = diagnostics.ActionRequiresEmptyPositionDiagnostic(
        location=_POS,
        action_name="action<my.domain.com:my_lib:/other>",
        position_name="position<box>::action</other>::position<item>",
        inferred_at=ast.SourcePosition(
            line=7,
            column=37,
            end_line=7,
            end_column=51,
            file_path=PurePosixPath("other.dfn"),
        ),
        propagated_from_locations=[],
        filled_at=_POS,
    )

    assert diagnostic.formatted_inferred_at == (
        'This requirement happens because of:\nFile "other.dfn", line 7, column 37'
    )


def test_formatted_inferred_at_with_propagated_from_locations():
    diagnostic = diagnostics.ActionRequiresEmptyPositionDiagnostic(
        location=_POS,
        action_name="action<my.domain.com:my_lib:/inner>",
        position_name="position<box>::action</outer>::position<iface>::action</inner>::position<item>",
        inferred_at=ast.SourcePosition(
            line=11,
            column=37,
            end_line=11,
            end_column=91,
            file_path=PurePosixPath("outer.dfn"),
        ),
        propagated_from_locations=[
            ast.SourcePosition(
                line=11,
                column=37,
                end_line=11,
                end_column=95,
                file_path=PurePosixPath("middle.dfn"),
            ),
            ast.SourcePosition(
                line=7,
                column=37,
                end_line=7,
                end_column=51,
                file_path=PurePosixPath("inner.dfn"),
            ),
        ],
        filled_at=_POS,
    )

    assert diagnostic.formatted_inferred_at == (
        "This requirement happens because of:\n"
        'File "outer.dfn", line 11, column 37\n'
        '  File "middle.dfn", line 11, column 37\n'
        '    File "inner.dfn", line 7, column 37'
    )
