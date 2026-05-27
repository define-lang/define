# pyright: reportUnusedCallResult=false
"""Test helpers specific to reference_graph_validator_tests."""

from pathlib import PurePosixPath
from pprint import pformat
from typing import TypedDict

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract


class ExpectedPropagationStep(TypedDict):
    """Expected per-step data for an entry in a requirement's propagation chain."""

    kind: action_contract.PropagationKind
    enclosing_quality_name: str
    triggered_quality_name: str | None
    line: int
    column: int
    file_path: str


def assert_propagation_chain(
    diag: diagnostics.RequirementDiagnostic,
    *expected_steps: ExpectedPropagationStep,
) -> None:
    """Assert a requirement diagnostic's full propagation chain, outer to inner."""
    __tracebackhide__ = True
    actual = [
        {
            "kind": step.kind,
            "enclosing_quality_name": step.enclosing_quality_name,
            "triggered_quality_name": step.triggered_quality_name,
            "line": step.location.line,
            "column": step.location.column,
            "file_path": step.location.file_path,
        }
        for step in diag.propagation_chain
    ]
    expected = [
        {
            "kind": entry["kind"],
            "enclosing_quality_name": entry["enclosing_quality_name"],
            "triggered_quality_name": entry["triggered_quality_name"],
            "line": entry["line"],
            "column": entry["column"],
            "file_path": PurePosixPath(entry["file_path"]),
        }
        for entry in expected_steps
    ]
    assert actual == expected, (
        f"propagation chain mismatch:\nactual:\n{pformat(actual)}\n"
        f"expected:\n{pformat(expected)}"
    )
