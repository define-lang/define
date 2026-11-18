from __future__ import annotations

from tools.bazel_mutation_testing.testdata.rust.killed_by_py_test import extension


def test_larger():
    assert extension.is_larger(2, 1)


def test_equal():
    assert not extension.is_larger(1, 1)


def test_smaller():
    assert not extension.is_larger(1, 2)
