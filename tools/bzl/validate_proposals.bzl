"""Proposal validation test macro."""

load("@aspect_rules_py//py:defs.bzl", _py_test = "py_test")

def validate_proposals_test(name, proposals, **kwargs):
    """Validate this package's proposal files.

    Args:
        name: Test target name.
        proposals: Label of the proposal files.
        **kwargs: Additional arguments passed to py_test.
    """
    _py_test(
        name = name,
        main = "//tools:validate_proposals.py",
        args = ["$(rlocationpaths %s)" % proposals],
        data = [proposals],
        deps = ["//tools:validate_proposals"],
        **kwargs
    )
