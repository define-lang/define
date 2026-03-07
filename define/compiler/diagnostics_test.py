from define.compiler import ast, diagnostics

_POS = ast.SourcePosition(line=3, column=5, end_line=3, end_column=12)


def test_circular_reference_message_lists_each_name():
    diagnostic = diagnostics.CircularGlobalReferenceDiagnostic(
        position=_POS,
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
        position=_POS,
        position_name="position<target>",
    )

    assert diagnostic.message == (
        "cannot move a dimension point to 'position<target>'"
        " because it already contains one"
    )


def test_move_to_occupied_message_with_line_number():
    diagnostic = diagnostics.MoveToOccupiedPositionDiagnostic(
        position=_POS,
        position_name="position<target>",
        occupied_at_line=9,
    )

    assert diagnostic.message == (
        "cannot move a dimension point to 'position<target>'"
        " because it already contains one; it was put there on line 9"
    )
