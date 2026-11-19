from __future__ import annotations

from tools.bazel_mutation_testing.testdata.python.times_out import lib


def test_reaches_limit():
    assert lib.first_multiple_from(3, 9) == 9
