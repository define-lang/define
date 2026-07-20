# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataNonFilesystemWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


class TestTriggerConditionValidation:
    def test_valid_local_name(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert_no_errors(result)

    def test_undefined_local_name(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        diags = result.file_results[0].diagnostics
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<unknown>"
        assert diags[0].location.line == 3
        assert diags[0].location.column == 13

    def test_invalid_local_name_format(
        self,
        validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
    ):
        result = validate_testdata_non_filesystem_with_reference_graph()
        assert result.all_exceptions == []
        diags = result.file_results[0].diagnostics
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
        assert diags[0].local_name == "position<BAD>"
        assert diags[0].location.line == 3
        assert diags[0].location.column == 13
        assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert diags[1].local_name == "BAD"
        assert diags[1].char == "B"
        assert diags[1].location.line == 3
        assert diags[1].location.column == 22
