"""Format test macro with git attribute checks disabled for Bazel sandbox compatibility."""

load("@aspect_rules_lint//format:defs.bzl", _format_test = "format_test")

def format_test(**kwargs):
    _format_test(
        disable_git_attribute_checks = True,
        **kwargs
    )
