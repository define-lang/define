from __future__ import annotations

from tools.bazel_mutation_testing import bazel


def test_query_expression_of_patterns():
    assert (
        bazel.query_expression(
            ["//define/...", "-//define/examples/...", "//crates/..."]
        )
        == "//define/... - //define/examples/... + //crates/..."
    )
