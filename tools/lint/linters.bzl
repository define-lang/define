load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@aspect_rules_lint//lint:ruff_bin"),
    configs = [
        Label("//:pyproject.toml"),
        Label("//compiler:pyproject.toml"),
        Label("//defcl:pyproject.toml"),
        Label("//tools:pyproject.toml"),
    ],
)
