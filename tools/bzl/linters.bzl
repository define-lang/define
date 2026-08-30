"""Linter rules for the codebase."""

load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@multitool//tools/ruff"),
    configs = [Label("//:pyproject.toml")],
    rule_kinds = [
        "py_binary",
        "py_library",
        "py_test",
        "py_venv_exec",
        "py_venv_exec_test",
    ],
)
