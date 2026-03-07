"""Project py_test macro with pytest_main enabled by default."""

load("@aspect_rules_py//py:defs.bzl", _py_test = "py_test")

def py_test(name, **kwargs):
    """Wraps aspect_rules_py's py_test with pytest_main always enabled.

    Args:
      name: Name of the test target.
      **kwargs: Additional arguments passed through to aspect_rules_py's
        `py_test`.
    """
    if "pytest_main" in kwargs:
        fail("Do not set pytest_main on //tools/bzl:py_test.bzl py_test targets.")

    deps = kwargs.pop("deps", [])
    if "@pypi//pytest" not in deps:
        deps = deps + ["@pypi//pytest"]

    _py_test(
        name = name,
        deps = deps,
        pytest_main = True,
        **kwargs
    )
