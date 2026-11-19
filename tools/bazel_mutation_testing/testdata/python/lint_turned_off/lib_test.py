from __future__ import annotations

from tools.bazel_mutation_testing.testdata.python.lint_turned_off import lib


def test_label_of_capitals():
    assert lib.label("NAME") == "NAME"
