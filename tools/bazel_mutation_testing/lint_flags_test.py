from __future__ import annotations

from tools.bazel_mutation_testing import lint_flags

_FLAGS = lint_flags.Flags(rustc=[], clippy=[])


def test_bazel_flags_name_each_tool_with_turned_off_rules():
    flags = lint_flags.LintFlags(
        repository=_FLAGS,
        mutation_run=_FLAGS,
        turned_off=lint_flags.TurnedOff(
            rust=frozenset({"unused_variables", "dead_code"}),
            ruff=frozenset({"F841"}),
            ast_grep=frozenset(),
            pyright=frozenset({"reportUnusedVariable"}),
        ),
    )
    assert flags.bazel_flags() == [
        "--//tools/bzl:allowed_rust_lints=dead_code,unused_variables",
        "--//tools/bzl:turned_off_pyright_rules=reportUnusedVariable",
        "--//tools/bzl:turned_off_ruff_rules=F841",
    ]
