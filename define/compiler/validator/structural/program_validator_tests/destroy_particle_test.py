# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import structural_diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.structural_validation import (
        ValidateTestdataStructuralNonFilesystem,
    )

pytest_plugins = ["define.compiler.test_fixtures.structural_validation"]


def test_valid_destroy_in_action_body(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_undefined_local_position_in_destroy(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.sorted_diagnostics()
    assert len(diags) == 1
    assert isinstance(diags[0], structural_diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].location.line == 5
    assert diags[0].location.column == 33
    assert diags[0].location.file_path is None
    assert diags[0].local_name == "position<undefined>"


def test_non_self_ref_global_in_action_body(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.sorted_diagnostics()
    assert len(diags) == 2
    assert isinstance(diags[0], structural_diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].source_global_name == "action</other>"
    assert diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert diags[0].location.line == 5
    assert diags[0].location.column == 33
    assert isinstance(
        diags[1],
        structural_diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic,
    )
    assert diags[1].location.file_path is None
    assert diags[1].definition_name == "action</other>"
    assert diags[1].config_path == ".define/project/config.defcl"
    assert diags[1].location.line == 5
    assert diags[1].location.column == 33
