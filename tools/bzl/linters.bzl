"""Linter rules for the codebase."""

load("//tools/bzl:ast_grep.bzl", "lint_ast_grep_aspect")
load("//tools/bzl:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@multitool//tools/ruff"),
    config = Label("//:pyproject.toml"),
    rule_kinds = [
        "py_binary",
        "py_library",
        "py_test",
        "py_venv_exec",
        "py_venv_exec_test",
    ],
)

ast_grep = lint_ast_grep_aspect(
    binary = Label("@multitool//tools/ast-grep"),
    config = Label("//:sgconfig.yml"),
    rules = Label("//checks:rules"),
    rule_kinds = [
        "py_binary",
        "py_library",
        "py_test",
        "py_venv_exec",
        "py_venv_exec_test",
        # The Rust library of each pyo3_extension.
        "rust_cdylib_library",
    ],
)
