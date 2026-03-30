# pyright: reportUnusedCallResult=false
from define.compiler.conftest import ValidateProject


class TestActionTriggering:
    def test_trigger_positions_recorded(
        self,
        validate_project: ValidateProject,
    ):
        result = validate_project(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<my_pos>.\n"
                    "    it happens when {\n"
                    "        the position<my_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.has_errors()
        all_trigger_positions = [
            tp
            for r in result.file_results
            for dr in r.definition_results
            for tp in dr.trigger_positions
        ]
        assert len(all_trigger_positions) == 1
        tp = all_trigger_positions[0]
        assert (
            tp.enclosing_typed_name.source_typed_name
            == "action<my.domain.com:my_lib:/test>"
        )
        assert len(tp.checked_position.typed_names) == 1
        assert (
            tp.checked_position.typed_names[0].source_typed_name == "position<my_pos>"
        )
