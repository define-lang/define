"""Diagnostic collection tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics

if TYPE_CHECKING:
    from define.compiler.test_fixtures.structural_validation import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )

pytest_plugins = ["define.compiler.test_fixtures.structural_validation"]


def test_multiple_diagnostics_collected(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.sorted_diagnostics()
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"


def test_diagnostics_in_source_order(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    diags = result.sorted_diagnostics()
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].location.file_path is None
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].reserved_name == "standard"
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].location.file_path is None
    assert diags[1].location.line == 2
    assert diags[1].location.column == 31
    assert diags[1].reserved_name == "standard"


def test_non_filesystem_source_reports_trailing_space_but_not_indentation(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.sorted_diagnostics() == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=9, column=60, end_line=9, end_column=61
            )
        )
    ]


def test_program_diagnostics_in_file_order(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert result.sorted_diagnostics() == [
        diagnostics.SubRootFqunMismatchDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=19,
                end_line=2,
                end_column=37,
                file_path="alpha/.define/project/config.defcl",
            ),
            expected_fqun="alpha.com:alpha_lib",
            actual_fqun="alpha.com:wrong_lib",
            sub_root_path="alpha",
        ),
        diagnostics.SubRootFqunMismatchDiagnostic(
            location=rendering.SourceLocation(
                line=2,
                column=19,
                end_line=2,
                end_column=36,
                file_path="zeta/.define/project/config.defcl",
            ),
            expected_fqun="zeta.com:zeta_lib",
            actual_fqun="zeta.com:wrong_lib",
            sub_root_path="zeta",
        ),
    ]
