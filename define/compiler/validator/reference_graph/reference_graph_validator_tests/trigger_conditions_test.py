# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
)


class TestTriggerConditionValidation:
    def test_valid_local_name(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<my_pos>.\n"
            "    it happens when {\n"
            "        the position<my_pos> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert diags == []

    def test_undefined_local_name(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "        the position<unknown> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<unknown>"
        assert diags[0].location.line == 3
        assert diags[0].location.column == 22

    def test_invalid_local_name_format(
        self,
        validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "        the position<BAD> has a particle.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a particle in position<_noop>.\n"
            "    }\n"
            "}\n"
        )
        results = validate_non_filesystem_with_reference_graph(source).file_results
        diags = results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<BAD>"
        assert diags[0].location.line == 3
        assert diags[0].location.column == 22
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "BAD"
        assert diags[1].char == "B"
        assert diags[1].location.line == 3
        assert diags[1].location.column == 22
