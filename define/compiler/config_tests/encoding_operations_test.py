"""Loading a project's Encoding Operation associations."""

from __future__ import annotations

import typing

from crates.source_rendering.python import rendering
from define.compiler.config import (
    association_config,
    encoding_operations_config,
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


def test_resolves_encoding_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    () = table_diagnostics
    assert test_helpers.associated_names(table.value_encodings) == {}
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/add>": [
            (
                "/number/integer/add",
                test_helpers.encoding_operation_name_location("/number/integer/add", 6),
                [
                    ("a", "/number/integer/ascii"),
                    ("b", "/number/integer/ascii"),
                    ("result", "/number/integer/ascii"),
                ],
            ),
            (
                "other.com:lib:/number/natural/add",
                test_helpers.encoding_operation_name_location(
                    "other.com:lib:/number/natural/add", 26
                ),
                [
                    ("a", "other.com:lib:/number/natural/ascii"),
                    ("b", "other.com:lib:/number/natural/ascii"),
                    ("result", "other.com:lib:/number/natural/ascii"),
                ],
            ),
        ],
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 46
                ),
                [("a", "/number/integer/ascii"), ("result", "/number/integer/ascii")],
            ),
        ],
    }


def test_missing_encoding_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings={}, encoding_operations=None
        ),
        [
            config_diagnostics.EncodingOperationsConfigNotFoundDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE,
                    ("project", "associations", "has_encoding_operations"),
                ),
                encoding_operations_config_path=str(
                    encoding_operations_config.CONFIG_FILE.path
                ),
            )
        ],
    )


def test_logical_operation_in_another_universe_with_own_encoding(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    () = table_diagnostics
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<other.com:lib:/number/add>": [
            (
                "/number/integer/add",
                test_helpers.encoding_operation_name_location("/number/integer/add", 6),
                [
                    ("a", "/number/integer/ascii"),
                    ("b", "/number/integer/ascii"),
                    ("result", "/number/integer/ascii"),
                ],
            ),
        ],
    }


def test_logical_operation_in_another_universe_without_own_encoding(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.AssociationWithoutOwnDefinitionDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=27,
            end_line=4,
            end_column=51,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        ),
        logical_operation="logical_operation<other.com:lib:/number/add>",
        fqun="test.example.com:my_lib",
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_sorted_by_written_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    # "/number/add" sorts before "other.com:lib:/number/negate" as written,
    # but the full typed names sort the other way.
    () = table_diagnostics
    assert list(
        test_helpers.associated_encoding_operations(table.encoding_operations)
    ) == [
        "logical_operation<test.example.com:my_lib:/number/add>",
        "logical_operation<other.com:lib:/number/negate>",
    ]


def test_logical_operation_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=4,
            column=27,
            end_line=4,
            end_column=36,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        )
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_logical_operation_full_name_in_own_universe(
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
                column=27,
                end_line=4,
                end_column=49,
                file_path=str(encoding_operations_config.CONFIG_FILE.path),
            ),
            fqun="test.example.com:my_lib",
        )
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_view_encoding_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=14,
            column=24,
            end_line=14,
            end_column=43,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        )
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_encoding_operation_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=6,
            column=16,
            end_line=6,
            end_column=33,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        )
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/multiply>": [
            (
                "/number/integer/multiply",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/multiply", 26
                ),
                [
                    ("a", "/number/integer/ascii"),
                    ("b", "/number/integer/ascii"),
                    ("result", "/number/integer/ascii"),
                ],
            ),
        ],
    }


def test_encoding_operation_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert (
        diagnostic
        == structural_diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
            location=rendering.SourceLocation(
                line=6,
                column=16,
                end_line=6,
                end_column=38,
                file_path=str(encoding_operations_config.CONFIG_FILE.path),
            ),
            fqun="test.example.com:my_lib",
        )
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_unsorted_logical_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.UnsortedEncodingOperationDiagnostic(
        location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 1, "logical_operation"),
        ),
        abstract_operation="logical_operation</number/add>",
        previous_abstract_operation="logical_operation</number/negate>",
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 6
                ),
                [("a", "/number/integer/ascii"), ("result", "/number/integer/ascii")],
            ),
        ],
        "logical_operation<test.example.com:my_lib:/number/add>": [
            (
                "/number/integer/add",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/add", 22
                ),
                [
                    ("a", "/number/integer/ascii"),
                    ("b", "/number/integer/ascii"),
                    ("result", "/number/integer/ascii"),
                ],
            ),
        ],
    }


def test_duplicate_encoding_operation(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.DuplicateEncodingOperationDiagnostic(
        location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 1),
        ),
        abstract_operation="logical_operation</number/add>",
        encoding_operation="/number/integer/add",
        first_location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 0),
        ),
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/add>": [
            (
                "/number/integer/add",
                test_helpers.encoding_operation_name_location("/number/integer/add", 6),
                [
                    ("a", "/number/integer/ascii"),
                    ("b", "/number/integer/ascii"),
                    ("result", "/number/integer/ascii"),
                ],
            ),
            (
                "/number/natural/add",
                test_helpers.encoding_operation_name_location(
                    "/number/natural/add", 46
                ),
                [
                    ("a", "/number/natural/ascii"),
                    ("b", "/number/natural/ascii"),
                    ("result", "/number/natural/ascii"),
                ],
            ),
        ],
    }


def test_encoding_operation_missing(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings={}, encoding_operations=None
        ),
        [
            config_diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    encoding_operations_config.CONFIG_FILE,
                    (
                        "encoding_operations",
                        "operation_encodings",
                        0,
                        "encoding_operation",
                    ),
                ),
                field_path=(
                    "encoding_operations",
                    "operation_encodings",
                    0,
                    "encoding_operation",
                ),
                violation_message="value is required",
            )
        ],
    )


def test_encoding_operation_in_unconfigured_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    # Association resolution reports an unconfigured universe when it uses an
    # association, so loading the config keeps both associations.
    assert table_diagnostics == []
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "other.com:lib:/number/natural/negate",
                test_helpers.encoding_operation_name_location(
                    "other.com:lib:/number/natural/negate", 6
                ),
                [
                    ("a", "other.com:lib:/number/natural/ascii"),
                    ("result", "other.com:lib:/number/natural/ascii"),
                ],
            ),
            (
                "other.com:lib:/number/natural/negate_twice",
                test_helpers.encoding_operation_name_location(
                    "other.com:lib:/number/natural/negate_twice", 22
                ),
                [
                    ("a", "other.com:lib:/number/natural/binary"),
                    ("result", "other.com:lib:/number/natural/binary"),
                ],
            ),
        ]
    }


def test_abstract_operation_missing(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_association_table() == (
        association_config.AssociationTable(
            value_encodings={}, encoding_operations=None
        ),
        [
            config_diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    encoding_operations_config.CONFIG_FILE,
                    ("encoding_operations", "operation_encodings", 0),
                ),
                field_path=(
                    "encoding_operations",
                    "operation_encodings",
                    0,
                    "abstract_operation",
                ),
                violation_message="exactly one field is required in oneof",
            )
        ],
    )


def test_resolves_value_operation_encoding_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    # A logical operation and a Value Operation with the same name are
    # different Abstract Operations, so associating both with the same
    # Encoding Operation is not a duplicate.
    () = table_diagnostics
    negate_views = [("a", "/number/integer/ascii"), ("result", "/number/integer/ascii")]
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 6
                ),
                negate_views,
            ),
        ],
        "operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 22
                ),
                negate_views,
            ),
        ],
        "operation<test.example.com:my_lib:/number/negate_twice>": [
            (
                "/number/integer/negate_twice",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate_twice", 38
                ),
                negate_views,
            ),
        ],
    }


def test_unsorted_abstract_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    # "/number/add" sorts before "/number/negate", but the typed names
    # sort the other way.
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.UnsortedEncodingOperationDiagnostic(
        location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 1, "logical_operation"),
        ),
        abstract_operation="logical_operation</number/negate>",
        previous_abstract_operation="operation</number/add>",
    )
    negate_views = [("a", "/number/integer/ascii"), ("result", "/number/integer/ascii")]
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 22
                ),
                negate_views,
            ),
        ],
        "operation<test.example.com:my_lib:/number/add>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 6
                ),
                negate_views,
            ),
        ],
    }


def test_value_operation_in_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=19,
            end_line=4,
            end_column=46,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        ),
        field_name="operation",
        name="other.com:lib:/number/negate",
        fqun="test.example.com:my_lib",
    )
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {}


def test_associations_with_same_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    table, table_diagnostics = test_helpers.load_association_table()
    (diagnostic,) = table_diagnostics
    assert diagnostic == config_diagnostics.DuplicateAssociationEncodingsDiagnostic(
        location=test_helpers.encoding_operation_name_location(
            "/number/integer/negate_twice", 22
        ),
        abstract_operation="logical_operation</number/negate>",
        encoding_operation="/number/integer/negate_twice",
        first_encoding_operation="/number/integer/negate",
        first_location=test_helpers.encoding_operation_name_location(
            "/number/integer/negate", 6
        ),
    )
    negate_views = [("a", "/number/integer/ascii"), ("result", "/number/integer/ascii")]
    assert test_helpers.associated_encoding_operations(table.encoding_operations) == {
        "logical_operation<test.example.com:my_lib:/number/negate>": [
            (
                "/number/integer/negate",
                test_helpers.encoding_operation_name_location(
                    "/number/integer/negate", 6
                ),
                negate_views,
            ),
        ],
    }
