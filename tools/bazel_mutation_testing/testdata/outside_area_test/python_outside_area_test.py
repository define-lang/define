from __future__ import annotations

from tools.bazel_mutation_testing.testdata.python.outside_area import lib


def test_larger():
    assert lib.is_larger(2, 1)


def test_equal():
    assert not lib.is_larger(1, 1)
