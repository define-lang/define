"""Project py_test macro using pytest."""

load("@aspect_rules_py//py:defs.bzl", "py_pytest_test")

def py_test(name, **kwargs):
    """Wraps aspect_rules_py's pytest test driver.

    Args:
      name: Name of the test target.
      **kwargs: Additional arguments passed through to aspect_rules_py's
        `py_pytest_test`.
    """
    deps = kwargs.pop("deps", [])
    if "@pypi//pytest" not in deps:
        deps = deps + ["@pypi//pytest"]
    if "@pypi//coverage" not in deps:
        deps = deps + ["@pypi//coverage"]

    data = kwargs.pop("data", []) + ["//:pyproject.toml"]

    py_pytest_test(
        name = name,
        data = data,
        deps = deps,
        **kwargs
    )
