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

    # py_pytest_test eagerly converts deps to a list, so its deps cannot
    # contain a select(). These aliases make their non-coverage cases no-ops
    # by resolving to the pytest dependency already present above.
    deps = deps + [
        "//tools/bzl:coverage_pytest_dependency",
        "//tools/bzl:loop_coverage_pytest_dependency",
    ]

    data = kwargs.pop("data", []) + ["//:pyproject.toml"]
    env = kwargs.pop("env", {})
    coverage_env = dict(env)
    pytest_plugins = coverage_env.get("PYTEST_PLUGINS")
    if pytest_plugins:
        coverage_env["PYTEST_PLUGINS"] = pytest_plugins + ",tools.loop_coverage"
    else:
        coverage_env["PYTEST_PLUGINS"] = "tools.loop_coverage"
    env = select({
        "//tools/bzl:coverage_enabled": coverage_env,
        "//conditions:default": env,
    })

    py_pytest_test(
        name = name,
        data = data,
        deps = deps,
        env = env,
        **kwargs
    )
