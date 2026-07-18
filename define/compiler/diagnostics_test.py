from pathlib import PurePosixPath

from define.compiler import ast, diagnostics
from define.compiler.validator.reference_graph import action_contract

_LOC = ast.SourceLocation(line=3, column=5, end_line=3, end_column=12)


def test_circular_reference_message_lists_each_name():
    diagnostic = diagnostics.CircularGlobalReferenceDiagnostic(
        location=_LOC,
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
        location=_LOC,
        position_name="position<target>",
    )

    assert diagnostic.message == (
        "cannot move a particle to 'position<target>' because it already contains one"
    )


def test_move_to_occupied_message_with_position():
    diagnostic = diagnostics.MoveToOccupiedPositionDiagnostic(
        location=_LOC,
        position_name="position<target>",
        occupied_at=ast.SourceLocation(
            line=9,
            column=37,
            end_line=9,
            end_column=37,
            file_path=PurePosixPath("test.dfn"),
        ),
    )

    assert diagnostic.message == (
        "cannot move a particle to 'position<target>'"
        " because it already contains one; it was put there at:\n"
        'File "test.dfn", line 9, column 37'
    )


def test_move_from_empty_interface_position_default():
    diagnostic = diagnostics.MoveFromEmptyPositionDiagnostic(
        location=_LOC,
        position_name="position<box>::action</other>::position<item>",
        is_action_interface_position=True,
    )

    assert diagnostic.message == (
        "cannot move a particle from"
        " 'position<box>::action</other>::position<item>'"
        " because it does not contain one;"
        " action interface positions are empty by default"
    )


def test_move_from_empty_interface_position_with_inferred_at():
    diagnostic = diagnostics.MoveFromEmptyPositionDiagnostic(
        location=_LOC,
        position_name="position<box>::action</other>::position<trigger_pos>",
        is_action_interface_position=True,
        inferred_at=ast.SourceLocation(
            line=7,
            column=37,
            end_line=7,
            end_column=37,
            file_path=PurePosixPath("other.dfn"),
        ),
    )

    assert diagnostic.message == (
        "cannot move a particle from"
        " 'position<box>::action</other>::position<trigger_pos>'"
        " because it does not contain one; it was emptied at:\n"
        'File "other.dfn", line 7, column 37'
    )


def test_formatted_propagation_chain_with_single_root_step():
    diagnostic = diagnostics.InferredRequirementViolationDiagnostic(
        location=_LOC,
        required_empty=True,
        action_name="action<my.domain.com:my_lib:/other>",
        position_name="position<box>::action</other>::position<item>",
        propagation_chain=[
            action_contract.PropagationStep(
                location=ast.SourceLocation(
                    line=7,
                    column=37,
                    end_line=7,
                    end_column=51,
                    file_path=PurePosixPath("other.dfn"),
                ),
                kind=action_contract.PropagationKind.DIRECT_INFERENCE,
                enclosing_quality_name="action<my.domain.com:my_lib:/other>",
                triggered_quality_name=None,
            ),
        ],
    )

    assert diagnostic.formatted_propagation_chain == (
        "This error happens because:\n"
        "  'action<my.domain.com:my_lib:/other>' infers this requirement:\n"
        '    File "other.dfn", line 7, column 37'
    )


def test_formatted_propagation_chain_with_multi_step_trigger_chain():
    diagnostic = diagnostics.InferredRequirementViolationDiagnostic(
        location=_LOC,
        required_empty=True,
        action_name="action<my.domain.com:my_lib:/inner>",
        position_name="position<box>::action</outer>::position<iface>::action</inner>::position<item>",
        propagation_chain=[
            action_contract.PropagationStep(
                location=ast.SourceLocation(
                    line=11,
                    column=37,
                    end_line=11,
                    end_column=91,
                    file_path=PurePosixPath("outer.dfn"),
                ),
                kind=action_contract.PropagationKind.ACTION_TRIGGER,
                enclosing_quality_name="action<my.domain.com:my_lib:/outer>",
                triggered_quality_name="action<my.domain.com:my_lib:/middle>",
            ),
            action_contract.PropagationStep(
                location=ast.SourceLocation(
                    line=11,
                    column=37,
                    end_line=11,
                    end_column=95,
                    file_path=PurePosixPath("middle.dfn"),
                ),
                kind=action_contract.PropagationKind.ACTION_TRIGGER,
                enclosing_quality_name="action<my.domain.com:my_lib:/middle>",
                triggered_quality_name="action<my.domain.com:my_lib:/inner>",
            ),
            action_contract.PropagationStep(
                location=ast.SourceLocation(
                    line=7,
                    column=37,
                    end_line=7,
                    end_column=51,
                    file_path=PurePosixPath("inner.dfn"),
                ),
                kind=action_contract.PropagationKind.DIRECT_INFERENCE,
                enclosing_quality_name="action<my.domain.com:my_lib:/inner>",
                triggered_quality_name=None,
            ),
        ],
    )

    assert diagnostic.formatted_propagation_chain == (
        "This error happens because:\n"
        "  'action<my.domain.com:my_lib:/outer>' triggers"
        " 'action<my.domain.com:my_lib:/middle>':\n"
        '    File "outer.dfn", line 11, column 37\n'
        "  'action<my.domain.com:my_lib:/middle>' triggers"
        " 'action<my.domain.com:my_lib:/inner>':\n"
        '    File "middle.dfn", line 11, column 37\n'
        "  'action<my.domain.com:my_lib:/inner>' infers this requirement:\n"
        '    File "inner.dfn", line 7, column 37'
    )
