# pyright: reportUnusedCallResult=false
"""Test helpers specific to reference_graph_validator_tests."""

from pathlib import PurePosixPath
from pprint import pformat
from typing import TypedDict

from define.compiler import diagnostics


class InferredFromEntry(TypedDict):
    """Expected per-level data for an entry in a propagated_from chain."""

    full_typed_name: str
    line: int
    column: int
    file_path: str


def assert_propagation_chain(
    diag: diagnostics.ActionRequirementDiagnostic,
    *inferred_from: InferredFromEntry,
) -> None:
    """Assert a requirement diagnostic exposes the expected propagated_from chain."""
    __tracebackhide__ = True
    # TODO: Update ActionRequirementDiagnostic to actually have the names at each level.
    composed_tail = "::".join(
        entry["full_typed_name"] for entry in inferred_from if entry["full_typed_name"]
    )
    assert composed_tail == "" or diag.position_name.endswith(composed_tail), (
        f"per-level full_typed_name segments compose to {composed_tail!r},"
        f" but position_name {diag.position_name!r} does not end with that"
    )
    actual = [
        {
            "line": loc.line,
            "column": loc.column,
            "file_path": loc.file_path,
        }
        for loc in diag.propagated_from_locations
    ]
    expected = [
        {
            "line": entry["line"],
            "column": entry["column"],
            "file_path": PurePosixPath(entry["file_path"]),
        }
        for entry in inferred_from
    ]
    assert actual == expected, (
        f"propagated_from chain locations mismatch:\nactual:\n{pformat(actual)}\n"
        f"expected:\n{pformat(expected)}"
    )
