"""Loading a project's Value Encoding Associations."""

from __future__ import annotations

import typing

from crates.source_rendering.python import rendering
from define.compiler.config import (
    association_config,
    encoding_operations_config,
    encodings_config,
    project_config,
)
from define.compiler.config_tests import test_helpers
from define.compiler.errors import (
    config_diagnostics,
    structural_diagnostics,
    syntax_errors,
)

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest

pytest_plugins = ["define.compiler.test_fixtures.testdata"]


def test_resolves_value_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    () = table_diagnostics
    assert test_helpers.associated_names(table.value_encodings) == {
        "/number/integer": [
            test_helpers.encoding_name("/number/integer/twos_complement", 5)
        ],
        "/number/natural": [
            test_helpers.encoding_name("/number/integer/twos_complement", 9),
            test_helpers.encoding_name("/number/integer/unsigned", 13),
        ],
    }


def test_has_encodings_false_does_not_read_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings={},
            encoding_operations=encoding_operations_config.NO_ASSOCIATIONS,
        ),
        [],
    )


def test_missing_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings=None,
            encoding_operations=encoding_operations_config.NO_ASSOCIATIONS,
        ),
        [
            config_diagnostics.EncodingsConfigNotFoundDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE,
                    ("project", "associations", "has_encodings"),
                ),
                encodings_config_path=str(encodings_config.CONFIG_FILE.path),
            )
        ],
    )


def test_value_in_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=15,
            end_line=4,
            end_column=35,
            file_path=str(encodings_config.CONFIG_FILE.path),
        ),
        field_name="value",
        name="other.com:lib:/number",
        fqun="test.example.com:my_lib",
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_value_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=4,
            column=15,
            end_line=4,
            end_column=20,
            file_path=str(encodings_config.CONFIG_FILE.path),
        )
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_value_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert (
        diagnostic
        == structural_diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=rendering.SourceLocation(
                line=4,
                column=15,
                end_line=4,
                end_column=37,
                file_path=str(encodings_config.CONFIG_FILE.path),
            ),
            fqun="test.example.com:my_lib",
        )
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_resolves_encoding_from_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    () = table_diagnostics
    assert test_helpers.associated_names(table.value_encodings) == {
        "/number": [test_helpers.encoding_name("other.com:lib:/number/ascii", 5)]
    }


def test_encoding_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=29,
            file_path=str(encodings_config.CONFIG_FILE.path),
        )
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_encoding_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert (
        diagnostic
        == structural_diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=18,
                end_line=5,
                end_column=40,
                file_path=str(encodings_config.CONFIG_FILE.path),
            ),
            fqun="test.example.com:my_lib",
        )
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_unsorted_values(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.UnsortedValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            encodings_config.CONFIG_FILE, ("encodings", "value_encodings", 1, "value")
        ),
        value="/number/integer",
        previous_value="/number/natural",
    )
    assert test_helpers.associated_names(table.value_encodings) == {
        "/number/natural": [test_helpers.encoding_name("/number/natural/ascii", 5)],
        "/number/integer": [test_helpers.encoding_name("/number/integer/ascii", 9)],
    }


def test_duplicate_value_encoding(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.DuplicateValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            encodings_config.CONFIG_FILE, ("encodings", "value_encodings", 1)
        ),
        value="/number",
        encoding="/number/ascii",
        first_location=test_helpers.config_field_location(
            encodings_config.CONFIG_FILE, ("encodings", "value_encodings", 0)
        ),
    )
    assert test_helpers.associated_names(table.value_encodings) == {
        "/number": [test_helpers.encoding_name("/number/ascii", 5)],
        "/text": [test_helpers.encoding_name("/text/ascii", 13)],
    }


def test_duplicate_value_encoding_with_invalid_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    first_name, second_name, duplicate = table_diagnostics
    assert first_name == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=29,
            file_path=str(encodings_config.CONFIG_FILE.path),
        )
    )
    assert second_name == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=9,
            column=18,
            end_line=9,
            end_column=29,
            file_path=str(encodings_config.CONFIG_FILE.path),
        )
    )
    assert duplicate == config_diagnostics.DuplicateValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            encodings_config.CONFIG_FILE, ("encodings", "value_encodings", 1)
        ),
        value="/number",
        encoding="number/ascii",
        first_location=test_helpers.config_field_location(
            encodings_config.CONFIG_FILE, ("encodings", "value_encodings", 0)
        ),
    )
    assert test_helpers.associated_names(table.value_encodings) == {}


def test_encodings_only_in_unconfigured_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    # Both encodings are in the same universe, which is reported once.
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.ExternalUniverseNotConfiguredDiagnostic(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=30,
            file_path=str(encodings_config.CONFIG_FILE.path),
        ),
        universe="other.com:lib",
        current_universe_name="test.example.com:my_lib",
    )
    # The value quality is still associated with an encoding, so it keeps
    # its entry.
    assert test_helpers.associated_names(table.value_encodings) == {"/number": []}


def test_encoding_missing(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings=None,
            encoding_operations=encoding_operations_config.NO_ASSOCIATIONS,
        ),
        [
            config_diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    encodings_config.CONFIG_FILE,
                    ("encodings", "value_encodings", 0, "encoding"),
                ),
                field_path=("encodings", "value_encodings", 0, "encoding"),
                violation_message="value is required",
            )
        ],
    )
