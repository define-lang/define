"""Linter rules for the codebase."""

load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@multitool//tools/ruff"),
    configs = [
        Label("//:pyproject.toml"),
        Label("//define/compiler:pyproject.toml"),
        Label("//defcl:pyproject.toml"),
        Label("//tools:pyproject.toml"),
    ],
)
