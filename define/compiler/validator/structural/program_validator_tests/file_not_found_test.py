# pyright: reportUnusedCallResult=false
"""File not found validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path

import pytest

from define.compiler import diagnostics, exceptions
from define.compiler.conftest import (
    ParseAndValidateFile,
    ValidateProject,
)
from define.compiler.data_structures import define_path
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator


def test_entrypoint_file_not_found(validate_project: ValidateProject):
    result = validate_project({}, entry_file="nonexistent.dfn")
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
        "    it may only contain particles where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "missing.dfn"
    assert diag.location.line == 3
    assert diag.location.column == 29


def test_non_filesystem_cross_universe_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    child_universe = "mv:define-lang.org:child_lib"
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    test_helpers.write_local_deps_config(tmp_path, {child_universe: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", child_universe)
    (tmp_path / "lib" / "target.dfn").write_text(
        f"define the potential position<{child_universe}:/target>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        f"        it has the position<{child_universe}:/target>.\n"
        f"        it has the position<{child_universe}:/missing>.\n"
        "    }\n"
        "}\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "lib/missing.dfn"
    assert diag.location.line == 4
    assert diag.location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_forward_reference_within_non_filesystem_source_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Define requires definitions to appear before they are referenced; a forward
    # ref within one source is not recognized as same-file and the validator
    # mishandles it as an unconfigured cross-universe reference to the current
    # universe.
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)
    source = (
        "define the potential position<my.domain.com:my_lib:/a> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</b>.\n"
        "    }\n"
        "}\n"
        "define the potential position<my.domain.com:my_lib:/b>.\n"
    )
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    diag = diags[0]
    assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diag.universe == "my.domain.com:my_lib"
    assert diag.current_universe_name == "my.domain.com:my_lib"
    assert diag.location.line == 3
    assert diag.location.column == 29


def test_referenced_file_not_found_via_already_completed_target(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</missing>.\n"
                "        it has the position</target>.\n"
                "    }\n"
                "}\n"
            ),
            "target.dfn": (
                "define the potential position<my.domain.com:my_lib:/target> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</missing>.\n"
                "    }\n"
                "}\n"
            ),
        },
        max_workers=1,
    )
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].file_path == "missing.dfn"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0],
        diagnostics.ReferencedFileNotFoundDiagnostic,
    )
    assert result.file_results[1].diagnostics[0].file_path == "missing.dfn"


def test_referenced_file_not_found_for_two_definitions_in_same_file(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position</missing>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<local> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</missing>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<local> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    result = parse_and_validate_file(source)
    assert result.exception is None
    diags = result.diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert isinstance(diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "missing.dfn"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[1].file_path == "missing.dfn"
    assert diags[1].location.line == 9
    assert diags[1].location.column == 33
