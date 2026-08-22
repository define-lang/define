# pyright: reportUnusedCallResult=false
"""Parallel validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

import threading
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from unittest import mock

from define.compiler import diagnostics
from define.compiler.data_structures import define_path
from define.compiler.validator.structural import file_validator
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructural


def test_fan_out(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural(max_workers=4)
    assert len(result.file_results) == 11
    assert_no_errors(result)


def test_deep_chain(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural(max_workers=4)
    assert len(result.file_results) == 5
    assert_no_errors(result)


def test_diamond_dependency(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=4)
    assert len(result.file_results) == 4
    assert_no_errors(result)


def test_wrong_type_detected_without_deferral(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert result.all_exceptions == []
    assert len(result.file_results) == 4
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("hub.dfn")
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[2].diagnostics == []
    assert result.file_results[3].file_path == define_path.DefinePath("checker.dfn")
    assert len(result.file_results[3].diagnostics) == 1
    diag = result.file_results[3].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diag.location.line == 3
    assert diag.location.column == 29
    assert diag.file_path == "target.dfn"
    assert diag.definition_name == "position<my.domain.com:my_lib:/target>"


def test_reference_edges_resolve_by_file_completion_order(
    validate_testdata_structural: ValidateTestdataStructural,
):
    # With max_workers=2, test.dfn and lib/target.dfn run concurrently.
    # We force lib/target.dfn to complete after test.dfn so that
    # test.dfn's pending reference edges get resolved by the file
    # completion callback rather than being available immediately.
    original_validate_file = file_validator.FileStructuralValidator.validate_file
    test_completed = threading.Event()

    def ordered_validate_file(
        self: file_validator.FileStructuralValidator,
        context: file_validator.FileValidationContext,
    ):
        if context.full_path == PurePosixPath("target.dfn"):
            test_completed.wait()
        result = original_validate_file(self, context)
        if context.full_path == PurePosixPath("test.dfn"):
            test_completed.set()
        return result

    with mock.patch.object(
        file_validator.FileStructuralValidator,
        "validate_file",
        autospec=True,
        side_effect=ordered_validate_file,
    ):
        result = validate_testdata_structural(max_workers=2)

    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert len(result.file_results[0].diagnostics) == 2
    diag0 = result.file_results[0].diagnostics[0]
    assert isinstance(diag0, diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diag0.location.line == 3
    assert diag0.location.column == 29
    assert diag0.file_path == "lib/target.dfn"
    assert (
        diag0.definition_name == "position<mv:define-lang.org:test_parent:/lib/target>"
    )
    diag1 = result.file_results[0].diagnostics[1]
    assert isinstance(diag1, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag1.location.line == 4
    assert diag1.location.column == 29
    assert diag1.file_path == "target.dfn"
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert len(result.file_results[1].diagnostics) == 1
    diag2 = result.file_results[1].diagnostics[0]
    assert isinstance(diag2, diagnostics.PathMismatchDiagnostic)
    assert diag2.location.line == 1
    assert diag2.location.column == 62
    assert diag2.expected_path == "/lib/target"
    assert diag2.actual_path == "/target"
