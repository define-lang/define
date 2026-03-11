# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.conftest import (
    ParseAndValidateFile,
    ValidateProject,
)
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers


def test_entrypoint_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    result = program_validator.ProgramValidator().validate_program(
        PurePosixPath("nonexistent.def")
    )
    assert len(result.file_results) == 1
    assert isinstance(
        result.file_results[0].exception, exceptions.SourceFileNotFoundError
    )
    assert result.file_results[0].diagnostics == []


def test_referenced_file_not_found(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "missing.def"
    assert diag.position.line == 3
    assert diag.position.column == 29


def test_non_filesystem_cross_universe_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_universe = "mv:define-lang.org:child_lib"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_universe)
    (tmp_path / "lib" / "target.def").write_text(
        f"define the potential position<{child_universe}:/target>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        f"        it has the position<{child_universe}:/missing>.\n"
        "    }\n"
        "}\n"
    )
    result = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "lib/missing.def"
    assert diag.position.line == 4
    assert diag.position.column == 29
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")
    assert result.file_results[1].root_prefix == PurePosixPath("lib")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


# TODO: Both files get ReferencedFileNotFoundDiagnostic for the same missing
# file. Ideally we would only emit it once.
def test_referenced_file_not_found_via_already_completed_target(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.def": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</missing>.\n"
                "        it has the position</target>.\n"
                "    }\n"
                "}\n"
            ),
            "target.def": (
                "define the potential position<my.domain.com:my_lib:/target> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</missing>.\n"
                "    }\n"
                "}\n"
            ),
        },
        max_workers=1,
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == PurePosixPath("test.def")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].file_path == "missing.def"
    assert result.file_results[1].file_path == PurePosixPath("target.def")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[1].diagnostics[0].file_path == "missing.def"


def test_referenced_file_not_found_for_two_definitions_in_same_file(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<local> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</missing>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<local> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.def"
    assert diags[0].position.line == 3
    assert diags[0].position.column == 29
    assert diags[1].file_path == "missing.def"
    assert diags[1].position.line == 9
    assert diags[1].position.column == 33
