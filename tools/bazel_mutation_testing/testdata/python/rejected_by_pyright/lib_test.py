from __future__ import annotations

from tools.bazel_mutation_testing.testdata.python.rejected_by_pyright import lib


def test_total():
    assert lib.total([1, 2]) == 3
